let tabPool = [];
let tabTracker = new Map();
let processingTabs = new Map();
let isProcessing = false;
let processingCheckInterval = null;

const startProcessingCheck = () => {
    if (processingCheckInterval) clearInterval(processingCheckInterval);
    processingCheckInterval = setInterval(checkTabStatus, 3000);
};

const stopProcessingCheck = () => {
    if (processingCheckInterval) {
        clearInterval(processingCheckInterval);
        processingCheckInterval = null;
    }
};

const checkTabStatus = async () => {
    if (processingTabs.size === 0) {
        stopProcessingCheck();
        return;
    }

    for (const [fileId, tabInfo] of processingTabs.entries()) {
        try {
            const tab = await chrome.tabs.get(tabInfo.tabId);
            if (!tab || tab.status === 'unloaded') {
                await handleTabClosed(fileId, tabInfo);
            }
        } catch (error) {
            await handleTabClosed(fileId, tabInfo);
        }
    }
    
    // Also check for files that have been stuck too long (> 5 minutes)
    const now = Date.now();
    for (const [fileId, tabInfo] of processingTabs.entries()) {
        if (now - tabInfo.startTime > 300000) { // 5 minutes
            console.log(`File ${fileId} has been processing for over 5 minutes, marking as failed`);
            await handleTabClosed(fileId, tabInfo);
        }
    }
};

const handleTabClosed = async (fileId, tabInfo) => {
    processingTabs.delete(fileId);
    await window.filesModel.updateFileStatus(fileId, 'failed');
    
    if (processingTabs.size === 0) {
        window.isProcessing = false;
        await window.appModel.setButtonState(false);
        
        const btnStartProcess = document.getElementById('btn-start-process') || document.getElementById('start-btn-start-process');
        const btnStopProcess = document.getElementById('btn-stop-process') || document.getElementById('start-btn-stop-process');
        if (btnStartProcess && btnStopProcess) {
            btnStartProcess.style.display = 'inline-block';
            btnStopProcess.style.display = 'none';
        }
        
        if (window.broadcastStateChange) {
            window.broadcastStateChange({
                isProcessing: false,
                showStopButton: false,
                processComplete: true,
                message: 'Processing stopped - tabs closed'
            });
        }
        
        stopProcessingCheck();
    }
};

const addTabToTracking = (fileId, tabId) => {
    processingTabs.set(fileId, { tabId, startTime: Date.now() });
    startProcessingCheck();
};

const removeTabFromTracking = (fileId) => {
    processingTabs.delete(fileId);
    if (processingTabs.size === 0) {
        stopProcessingCheck();
    }
};

const stopAllProcessingTabs = async () => {
    console.log('Stopping all processing tabs and setting files to draft...');
    
    for (const [fileId, tabInfo] of processingTabs.entries()) {
        try {
            chrome.tabs.remove(tabInfo.tabId);
            await window.filesModel.updateFileStatus(fileId, 'draft', 0);
        } catch (error) {
            console.error(`Error closing tab ${tabInfo.tabId} for file ${fileId}:`, error);
        }
    }
    
    processingTabs.clear();
    stopProcessingCheck();
    
    window.isProcessing = false;
    window.shouldStopProcessing = true;
    
    await window.appModel.setButtonState(false);
    
    const btnStartProcess = document.getElementById('btn-start-process') || document.getElementById('start-btn-start-process');
    const btnStopProcess = document.getElementById('btn-stop-process') || document.getElementById('start-btn-stop-process');
    if (btnStartProcess && btnStopProcess) {
        btnStartProcess.style.display = 'inline-block';
        btnStopProcess.style.display = 'none';
    }
    
    if (window.broadcastStateChange) {
        window.broadcastStateChange({
            isProcessing: false,
            showStopButton: false,
            processComplete: false,
            message: 'Processing stopped by user'
        });
    }
};



// Helper function to find upload area - keep checking until found
async function findUploadArea(tabId) {
    let attempt = 0;
    while (true) {
        attempt++;
        console.log(`Tab ${tabId}: Finding upload area, attempt ${attempt}`);
        
        // Check if user wants to stop
        if (window.shouldStopProcessing) {
            console.log(`Tab ${tabId}: Stopping upload area search due to user request`);
            return false;
        }
        
        const found = await new Promise((resolve) => {
            chrome.scripting.executeScript({
                target: { tabId },
                func: function() {
                    return !!document.getElementById('uploadArea');
                }
            }, (results) => {
                if (chrome.runtime.lastError) {
                    console.error(`Tab ${tabId}: Script execution failed:`, chrome.runtime.lastError.message);
                    resolve(false);
                } else {
                    const found = results && results[0] && results[0].result;
                    resolve(found);
                }
            });
        });
        
        if (found) {
            console.log(`Tab ${tabId}: Upload area found on attempt ${attempt}`);
            return true;
        }
        
        console.log(`Tab ${tabId}: Upload area not found, waiting 1s before retry...`);
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}

// Helper function to upload file to tab - keep trying until success
async function uploadFileToTab(tabId, fileData, fileName, fileType) {
    let attempt = 0;
    while (true) {
        attempt++;
        console.log(`Tab ${tabId}: Uploading file, attempt ${attempt}`);
        
        // Check if user wants to stop
        if (window.shouldStopProcessing) {
            console.log(`Tab ${tabId}: Stopping upload due to user request`);
            return false;
        }
        
        const result = await new Promise((resolve) => {
            chrome.tabs.sendMessage(tabId, {
                type: 'upload-image',
                fileData: fileData,
                fileName: fileName,
                fileType: fileType
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.error(`Tab ${tabId}: Upload message failed:`, chrome.runtime.lastError.message);
                    resolve(false);
                } else {
                    resolve(response);
                }
            });
        });
        
        if (result && result.success) {
            console.log(`Tab ${tabId}: Upload successful on attempt ${attempt}`);
            return result;
        }
        
        console.log(`Tab ${tabId}: Upload failed, waiting 1s before retry...`);
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}

// Helper function to wait for result - keep checking until found
async function waitForResult(tabId) {
    let pollCount = 0;
    while (true) {
        pollCount++;
        console.log(`Tab ${tabId}: Waiting for result (${pollCount})`);
        
        // Check if user wants to stop
        if (window.shouldStopProcessing) {
            console.log(`Tab ${tabId}: Stopping result wait due to user request`);
            return null;
        }
        
        const result = await new Promise((resolve) => {
            chrome.scripting.executeScript({
                target: { tabId },
                func: function() {
                    const resultNodes = Array.from(document.querySelectorAll('[class*="Result-root"]'));
                    let found = false;
                    let details = [];
                    if (resultNodes.length) {
                        found = true;
                        details = resultNodes.map(node => node.className);
                    }
                    return { found, details };
                }
            }, (results) => {
                if (chrome.runtime.lastError) {
                    console.error(`Tab ${tabId}: Script injection failed:`, chrome.runtime.lastError.message);
                    resolve(null);
                } else {
                    const res = results && results[0] && results[0].result;
                    resolve(res);
                }
            });
        });
        
        if (result && result.found) {
            console.log(`Tab ${tabId}: Result found:`, result.details);
            return result.details;
        }
        
        console.log(`Tab ${tabId}: Result not found, waiting 1s before next check...`);
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}

// Helper function to download image
async function downloadImage(tabId, outputFolder, originalFileName) {
    return new Promise((resolve) => {
        chrome.scripting.executeScript({
            target: { tabId },
            func: function() {
                const resultNodes = Array.from(document.querySelectorAll('[class*="Result-root"]'));
                let imageSrc = null;
                
                for (const node of resultNodes) {
                    const img = node.querySelector('img');
                    if (img && img.src) {
                        imageSrc = img.src;
                        break;
                    }
                }
                
                return imageSrc;
            }
        }, (imgResults) => {
            const imageSrc = imgResults && imgResults[0] && imgResults[0].result;
            if (imageSrc) {
                console.log(`Tab ${tabId}: Attempting to download result:`, imageSrc);
                if (chrome.downloads) {
                    const filename = outputFolder + '/' + originalFileName;
                    console.log(`Tab ${tabId}: Downloading to:`, filename);
                    chrome.downloads.download({
                        url: imageSrc,
                        filename: filename,
                        saveAs: false
                    }, (downloadId) => {
                        if (chrome.runtime.lastError) {
                            console.error(`Tab ${tabId}: Download failed:`, chrome.runtime.lastError.message);
                            resolve(false);
                        } else {
                            console.log(`Tab ${tabId}: Download started, id:`, downloadId);
                            resolve(true);
                        }
                    });
                } else {
                    console.log(`Tab ${tabId}: Chrome downloads API not available`);
                    resolve(false);
                }
            } else {
                console.log(`Tab ${tabId}: No result image found`);
                resolve(false);
            }
        });
    });
}

// Helper function to process single file (without opening tab)
async function processFileInTab(tabId, file, outputFolder) {
    console.log(`Processing file ${file.name} in tab ${tabId}`);
    
    // Add tab to tracking
    addTabToTracking(file.name, tabId);
    
    // Check if user wants to stop
    if (window.shouldStopProcessing) {
        console.log(`Tab ${tabId}: Stopping processing due to user request`);
        await window.filesModel.updateFileStatus(file.name, 'draft', 0);
        removeTabFromTracking(file.name);
        return false;
    }

    await window.filesModel.updateFileStatus(file.name, 'Finding upload area...', 30);
    const uploadAreaFound = await findUploadArea(tabId);
    
    if (uploadAreaFound) {
        console.log(`Tab ${tabId}: Upload area found, uploading image...`);
        await window.filesModel.updateFileStatus(file.name, 'Uploading image...', 40);
        
        const uploadResult = await uploadFileToTab(tabId, file.data, file.name, file.type || 'image/png');
        
        if (uploadResult && uploadResult.success) {
            await window.filesModel.updateFileStatus(file.name, 'Processing image...', 60);
            const resultDetails = await waitForResult(tabId);
            
            if (resultDetails) {
                await window.filesModel.updateFileStatus(file.name, 'Downloading result...', 80);
                const downloadSuccess = await downloadImage(tabId, outputFolder, file.name);
                
                if (downloadSuccess) {
                    console.log(`Tab ${tabId}: Process completed successfully for ${file.name}`);
                    await window.filesModel.updateFileStatus(file.name, 'completed', 100);
                    removeTabFromTracking(file.name);
                    return true;
                } else {
                    console.log(`Tab ${tabId}: Download failed for ${file.name}`);
                    await window.filesModel.updateFileStatus(file.name, 'failed', 0);
                    removeTabFromTracking(file.name);
                    return false;
                }
            } else {
                console.log(`Tab ${tabId}: Result checking stopped for ${file.name}`);
                await window.filesModel.updateFileStatus(file.name, 'draft', 0);
                removeTabFromTracking(file.name);
                return false;
            }
        } else {
            console.log(`Tab ${tabId}: Upload stopped for ${file.name}`);
            await window.filesModel.updateFileStatus(file.name, 'draft', 0);
            removeTabFromTracking(file.name);
            return false;
        }
    } else {
        console.log(`Tab ${tabId}: Upload area search stopped for ${file.name}`);
        await window.filesModel.updateFileStatus(file.name, 'draft', 0);
        removeTabFromTracking(file.name);
        return false;
    }
}

// Helper function to open tab and wait for complete loading
async function openTabAndWaitForLoad(url) {
    return new Promise((resolve, reject) => {
        chrome.tabs.create({
            url: url,
            active: false
        }, function(tab) {
            if (!tab || !tab.id) {
                console.error('Failed to open tab');
                resolve(null);
                return;
            }

            console.log(`Tab ${tab.id}: Opened, waiting for complete load...`);
            let tabLoadCompleted = false;

            // Create listener for this specific tab
            const tabListener = function(tabId, info, tabObj) {
                if (tabId !== tab.id || tabLoadCompleted) return;
                
                if (info.status === 'complete') {
                    console.log(`Tab ${tab.id}: Page fully loaded and ready`);
                    tabLoadCompleted = true;
                    chrome.tabs.onUpdated.removeListener(tabListener);
                    
                    // Wait additional time for all scripts to load
                    setTimeout(() => {
                        resolve(tab);
                    }, 5000);
                }
            };
            
            chrome.tabs.onUpdated.addListener(tabListener);
            
            // Fallback timeout - if tab never loads properly
            setTimeout(() => {
                if (!tabLoadCompleted) {
                    console.log(`Tab ${tab.id}: Load timeout, removing listener`);
                    chrome.tabs.onUpdated.removeListener(tabListener);
                    resolve(tab); // Still return tab, let processing handle the rest
                }
            }, 30000); // 30 second timeout for loading
        });
    });
}

// Main batch processing function with improved tab management
async function openTabAndPrintUploadArea(selectedOutputFolder) {
    console.log('Starting batch processing...');
    
    if (!chrome || !chrome.tabs || !chrome.scripting) {
        console.error('Chrome API not available or missing permissions.');
        return;
    }

    // Reset stop flag
    window.shouldStopProcessing = false;

    // Get all files from IndexedDB (only draft files)
    let files = [];
    if (window.filesModel && window.filesModel.getAllFiles) {
        try {
            const allFiles = await window.filesModel.getAllFiles();
            files = allFiles.filter(f => f.status === 'draft' || !f.status);
        } catch (e) {
            console.error('Failed to get files from DB:', e);
            return;
        }
    }
    
    if (!files.length) {
        console.log('No draft files found to process.');
        window.isProcessing = false;
        window.shouldStopProcessing = false;
        
        console.log('No files to process, switching back to start button');
        const btnStartProcess = document.getElementById('btn-start-process');
        const btnStopProcess = document.getElementById('btn-stop-process');
        if (btnStartProcess && btnStopProcess) {
            btnStartProcess.style.display = 'inline-block';
            btnStopProcess.style.display = 'none';
        }
        return;
    }

    // Get batch size from UI (try start page first, then program page)
    const startBatchSizeInput = document.getElementById('start-batch-size-spinner');
    const programBatchSizeInput = document.getElementById('batch-size-spinner');
    const batchSizeInput = startBatchSizeInput || programBatchSizeInput;
    
    let batchSize = 5; // default
    if (batchSizeInput) {
        batchSize = parseInt(batchSizeInput.value, 10) || 5;
    } else {
        // Try to get from appModel if UI element not found
        try {
            const savedBatchSize = await window.appModel.getBatchSize();
            if (savedBatchSize) {
                batchSize = savedBatchSize;
            }
        } catch (e) {
            console.log('Could not get saved batch size, using default');
        }
    }
    
    console.log(`Found ${files.length} draft files, processing in batches of ${batchSize}`);
    
    // Split files into batches
    const totalBatches = Math.ceil(files.length / batchSize);
    let totalProcessed = 0;
    let totalSuccessful = 0;
    
    for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
        // Check if user requested stop before starting each batch
        if (window.shouldStopProcessing) {
            console.log('Processing stopped by user before batch');
            break;
        }
        
        const startIndex = batchIndex * batchSize;
        const endIndex = Math.min(startIndex + batchSize, files.length);
        const batchFiles = files.slice(startIndex, endIndex);
        
        console.log(`Starting batch ${batchIndex + 1} of ${totalBatches} (files ${startIndex + 1}-${endIndex})`);
        
        // PHASE 1: Open all tabs for current batch and wait for them to load completely
        console.log(`Phase 1: Opening ${batchFiles.length} tabs for batch ${batchIndex + 1}...`);
        const tabPromises = batchFiles.map(async (file, index) => {
            await window.filesModel.updateFileStatus(file.name, 'Opening tab...', 10);
            const tab = await openTabAndWaitForLoad('https://picsart.com/id/ai-image-enhancer/');
            if (tab) {
                await window.filesModel.updateFileStatus(file.name, 'Tab loaded, ready for processing...', 25);
                return { tab, file };
            } else {
                await window.filesModel.updateFileStatus(file.name, 'failed', 0);
                return null;
            }
        });
        
        // Wait for all tabs to open and load completely
        const tabResults = await Promise.all(tabPromises);
        const validTabs = tabResults.filter(result => result !== null);
        
        console.log(`Phase 1 complete: ${validTabs.length}/${batchFiles.length} tabs opened successfully`);
        
        if (validTabs.length === 0) {
            console.log('No tabs opened successfully in this batch, skipping...');
            continue;
        }
        
        // Check if user requested stop after opening tabs
        if (window.shouldStopProcessing) {
            console.log('Processing stopped by user after opening tabs, closing batch tabs...');
            for (const tabResult of validTabs) {
                chrome.tabs.remove(tabResult.tab.id);
                removeTabFromTracking(tabResult.file.name);
            }
            break;
        }
        
        // PHASE 2: Process all files in opened tabs simultaneously
        console.log(`Phase 2: Processing ${validTabs.length} files simultaneously...`);
        const processingPromises = validTabs.map(async (tabResult) => {
            const { tab, file } = tabResult;
            try {
                const success = await processFileInTab(tab.id, file, selectedOutputFolder);
                chrome.tabs.remove(tab.id);
                return success;
            } catch (error) {
                console.error(`Error processing file ${file.name} in tab ${tab.id}:`, error);
                await window.filesModel.updateFileStatus(file.name, 'failed', 0);
                removeTabFromTracking(file.name);
                chrome.tabs.remove(tab.id);
                return false;
            }
        });
        
        // Wait for all files in current batch to complete processing
        const batchResults = await Promise.all(processingPromises);
        const successCount = batchResults.filter(result => result).length;
        totalProcessed += batchResults.length;
        totalSuccessful += successCount;
        
        console.log(`Batch ${batchIndex + 1} completed: ${successCount}/${batchResults.length} files processed successfully`);
        console.log(`Total progress: ${totalProcessed}/${files.length} files processed, ${totalSuccessful} successful`);
        
        // Check if user requested stop after batch completion
        if (window.shouldStopProcessing) {
            console.log('Processing stopped by user after batch completion');
            break;
        }
        
        // Delay before next batch to ensure stability
        if (batchIndex < totalBatches - 1) {
            console.log('Waiting before starting next batch...');
            await new Promise(resolve => setTimeout(resolve, 3000)); // 3 second delay between batches
        }
    }
    
    // Reset processing state
    window.isProcessing = false;
    window.shouldStopProcessing = false;
    
    // Update database state to reflect completion
    await window.appModel.setProcessingState(false);
    await window.appModel.setButtonState(false);
    
    // Switch buttons back to start state
    console.log('Processing completed, switching back to start button');
    const btnStartProcess = document.getElementById('btn-start-process');
    const btnStopProcess = document.getElementById('btn-stop-process');
    if (btnStartProcess && btnStopProcess) {
        btnStartProcess.style.display = 'inline-block';
        btnStopProcess.style.display = 'none';
    }
    
    // Also update start page buttons if they exist
    const startBtnStartProcess = document.getElementById('start-btn-start-process');
    const startBtnStopProcess = document.getElementById('start-btn-stop-process');
    if (startBtnStartProcess && startBtnStopProcess) {
        startBtnStartProcess.style.display = 'inline-block';
        startBtnStopProcess.style.display = 'none';
    }
    
    // Broadcast state change for synchronization
    if (window.broadcastStateChange) {
        const outputPath = document.getElementById('output-folder-path') || document.getElementById('start-output-folder-path');
        const batchSizeElement = document.getElementById('start-batch-size-spinner') || document.getElementById('batch-size-spinner');
        window.broadcastStateChange({
            outputFolder: outputPath?.value?.trim() || '',
            batchSize: parseInt(batchSizeElement?.value, 10) || 5,
            isProcessing: false,
            showStopButton: false,
            processComplete: true
        });
    }
    
    if (window.shouldStopProcessing) {
        console.log(`Processing stopped by user. Processed ${totalProcessed}/${files.length} files, ${totalSuccessful} successful`);
    } else {
        console.log(`All batches completed! Processed ${totalProcessed}/${files.length} files, ${totalSuccessful} successful`);
    }
}

// Expose stop function globally
window.stopAllProcessingTabs = stopAllProcessingTabs;