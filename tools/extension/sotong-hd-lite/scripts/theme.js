// Display extension version from manifest.json in the popup footer
// Show/hide Start button based on active tab URL
document.addEventListener('DOMContentLoaded', function() {
	const root = document.getElementById('app-root');
	const header = document.getElementById('app-header');
	const footer = document.getElementById('app-footer');

	function loadComponent(target, url, callback) {
		fetch(url)
			.then(res => res.text())
			.then(html => {
				if (target) target.innerHTML = html;
				if (callback) callback();
			});
	}

	function loadPage(url, callback) {
		fetch(url)
			.then(res => res.text())
			.then(html => {
				if (root) root.innerHTML = html;
				if (callback) callback();
			});
	}

	loadComponent(header, 'pages/components/base/header.html');
	loadComponent(footer, 'pages/components/base/footer.html', () => {
		if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getManifest) {
			const manifest = chrome.runtime.getManifest();
			const version = manifest.version;
			const versionSpan = document.getElementById('app-version');
			if (versionSpan) {
				versionSpan.textContent = `Version ${version}`;
			}
		}
		const helpBtn = document.getElementById('help-btn');
		if (helpBtn) {
			helpBtn.addEventListener('click', function() {
				if (typeof chrome !== 'undefined' && chrome.tabs) {
					chrome.tabs.create({url: 'pages/help_page.html'});
				} else if (typeof browser !== 'undefined' && browser.tabs) {
					browser.tabs.create({url: 'pages/help_page.html'});
				} else {
					window.open('pages/help_page.html', '_blank');
				}
			});
		}
	});

	loadPage('pages/start_page.html', () => {
		initializeStartPage();
	});

	async function renderStats() {
		// Wait for filesModel to be available
		if (!window.filesModel) {
			if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL) {
				const script = document.createElement('script');
				script.src = chrome.runtime.getURL('pages/program/models/files_model.js');
				document.head.appendChild(script);
				script.onload = renderStats;
				return;
			}
			return;
		}
		const countSpan = document.getElementById('stats-file-count');
		const progressBar = document.getElementById('stats-progress-bar');
		if (!countSpan || !progressBar) return;
		let files = [];
		try {
			files = await window.filesModel.getAllFiles();
		} catch (e) {
			files = [];
		}
		const count = files.length;
		countSpan.textContent = count;
		// Find next power of ten chunk
		let chunk = 10;
		while (count >= chunk) {
			chunk *= 10;
		}
		const percent = Math.min(100, (count / chunk) * 100);
		progressBar.style.width = percent + '%';
		progressBar.textContent = count;
	}

	function initializeStartPage() {
		const navContainer = document.getElementById('navigation-container');
		if (!navContainer) return;

		// Load models first
		const loadModels = async () => {
			await Promise.all([
				new Promise((resolve) => {
					const script = document.createElement('script');
					script.src = 'pages/program/models/files_model.js';
					script.onload = resolve;
					document.head.appendChild(script);
				}),
				new Promise((resolve) => {
					const script = document.createElement('script');
					script.src = 'pages/program/models/app_model.js';
					script.onload = resolve;
					document.head.appendChild(script);
				}),
				new Promise((resolve) => {
					const script = document.createElement('script');
					script.src = 'pages/program/scripts/background_workers.js';
					script.onload = resolve;
					document.head.appendChild(script);
				}),
				new Promise((resolve) => {
					const script = document.createElement('script');
					script.src = 'pages/program/scripts/inject_upload.js';
					script.onload = resolve;
					document.head.appendChild(script);
				})
			]);
		};

		loadModels().then(() => {
			Promise.all([
				fetch('pages/components/start/navigation.html').then(response => response.text()),
				fetch('pages/components/start/actions.html').then(response => response.text()),
				fetch('pages/components/start/dnd_area.html').then(response => response.text())
			]).then(([navHtml, actionsHtml, dndHtml]) => {
				navContainer.innerHTML = navHtml + actionsHtml + dndHtml;
				setupNavigation();
				setupStartDndArea();
				setupStartActions();
				updateStartStats();
				restoreStartAppState();
			});
		});

		function setupNavigation() {
			const btnHome = document.getElementById('nav-home');
			const btnWhatsapp = document.getElementById('nav-whatsapp');
			
			if (btnHome) {
				btnHome.addEventListener('click', function() {
					if (typeof chrome !== 'undefined' && chrome.tabs) {
						chrome.tabs.create({url: 'pages/program/program_page.html'});
					} else {
						window.location.href = 'pages/program/program_page.html';
					}
				});
			}
			
			if (btnWhatsapp) {
				btnWhatsapp.addEventListener('click', function() {
					const waUrl = 'https://chat.whatsapp.com/CMQvDxpCfP647kBBA6dRn3';
					if (typeof chrome !== 'undefined' && chrome.tabs) {
						chrome.tabs.create({url: waUrl});
					} else {
						window.open(waUrl, '_blank');
					}
				});
			}
		}

		function setupStartDndArea() {
			const dropzone = document.getElementById('start-dnd-dropzone');
			const fileInput = document.getElementById('start-dnd-file-input');
			const folderInput = document.getElementById('start-dnd-folder-input');
			const btnSelectFiles = document.getElementById('start-btn-select-files');
			const btnSelectFolder = document.getElementById('start-btn-select-folder');
			const supportedTypes = [
				'image/jpeg',
				'image/png',
				'image/webp',
				'image/heic'
			];

			let startFileLoadingCancelled = false;

			btnSelectFiles.addEventListener('click', function() {
				fileInput.value = '';
				fileInput.click();
			});

			btnSelectFolder.addEventListener('click', function() {
				folderInput.value = '';
				folderInput.click();
			});

			dropzone.addEventListener('click', function(e) {
				if (e.target === dropzone) {
					fileInput.value = '';
					fileInput.click();
				}
			});

			dropzone.addEventListener('dragover', function(e) {
				e.preventDefault();
				dropzone.classList.add('bg-light');
			});

			dropzone.addEventListener('dragleave', function(e) {
				e.preventDefault();
				dropzone.classList.remove('bg-light');
			});

			dropzone.addEventListener('drop', async function(e) {
				e.preventDefault();
				dropzone.classList.remove('bg-light');
				const items = e.dataTransfer.items;
				let files = [];
				if (items && items.length > 0 && items[0].webkitGetAsEntry) {
					showStartFileLoadingModal();
					updateStartFileLoadingProgress(0, 1, 'Scanning folders...');
					
					const entries = [];
					for (let i = 0; i < items.length; i++) {
						const entry = items[i].webkitGetAsEntry();
						if (entry) entries.push(entry);
					}
					await Promise.all(entries.map(entry => readAllFilesFromEntry(entry, files)));
				} else {
					files = Array.from(e.dataTransfer.files);
				}
				await setStartFiles(files);
			});

			fileInput.addEventListener('change', async function(e) {
				await setStartFiles(Array.from(e.target.files));
			});

			folderInput.addEventListener('change', async function(e) {
				const files = Array.from(e.target.files);
				if (files.length > 10) {
					showStartFileLoadingModal();
					updateStartFileLoadingProgress(0, files.length, 'Preparing files...');
				}
				await setStartFiles(files);
			});

			async function setStartFiles(files) {
				if (!files || files.length === 0) return;
				
				if (files.length > 10) {
					showStartFileLoadingModal();
				}
				
				const existingFiles = await window.filesModel.getAllFiles();
				const existingNames = new Set(existingFiles.map(f => f.name));
				const newFiles = files.filter(f => f.name && !existingNames.has(f.name));
				
				if (newFiles.length > 0) {
					if (newFiles.length > 10) {
						await processStartFilesWithProgress(newFiles);
					} else {
						await window.filesModel.addFiles(newFiles);
					}
				}
				
				hideStartFileLoadingModal();
				updateStartStats();
			}

			function showStartFileLoadingModal() {
				startFileLoadingCancelled = false;
				const modal = document.getElementById('start-file-loading-modal');
				const cancelBtn = document.getElementById('start-btn-cancel-file-loading');
				
				if (cancelBtn) {
					cancelBtn.onclick = function() {
						startFileLoadingCancelled = true;
						hideStartFileLoadingModal();
					};
				}
				
				if (modal) {
					if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
						const bootstrapModal = new bootstrap.Modal(modal);
						bootstrapModal.show();
					} else {
						modal.style.display = 'block';
						modal.classList.add('show');
					}
				}
			}

			function hideStartFileLoadingModal() {
				const modal = document.getElementById('start-file-loading-modal');
				if (modal) {
					if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
						const bootstrapModal = bootstrap.Modal.getInstance(modal);
						if (bootstrapModal) {
							bootstrapModal.hide();
						}
					} else {
						modal.style.display = 'none';
						modal.classList.remove('show');
					}
				}
			}

			function updateStartFileLoadingProgress(current, total, fileName = '') {
				const progressText = document.getElementById('start-file-progress-text');
				const progressBar = document.getElementById('start-file-progress-bar');
				const progressPercentage = document.getElementById('start-file-progress-percentage');
				const currentFileInfo = document.getElementById('start-current-file-info');
				
				if (progressText) progressText.textContent = `${current}/${total} files`;
				
				const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
				if (progressBar) progressBar.style.width = `${percentage}%`;
				if (progressPercentage) progressPercentage.textContent = `${percentage}%`;
				
				if (currentFileInfo && fileName) {
					currentFileInfo.textContent = `Processing: ${fileName}`;
				}
			}

			async function processStartFilesWithProgress(files) {
				const chunkSize = 5;
				let processed = 0;
				
				for (let i = 0; i < files.length; i += chunkSize) {
					if (startFileLoadingCancelled) {
						console.log('Start file loading cancelled by user');
						break;
					}
					
					const chunk = files.slice(i, i + chunkSize);
					
					for (const file of chunk) {
						if (startFileLoadingCancelled) break;
						
						updateStartFileLoadingProgress(processed + 1, files.length, file.name);
						processed++;
						
						await new Promise(resolve => setTimeout(resolve, 10));
					}
					
					if (!startFileLoadingCancelled) {
						await window.filesModel.addFiles(chunk);
					}
					
					await new Promise(resolve => setTimeout(resolve, 100));
				}
				
				if (!startFileLoadingCancelled) {
					updateStartFileLoadingProgress(files.length, files.length, 'Complete!');
				}
			}

			async function readAllFilesFromEntry(entry, files) {
				if (entry.isFile) {
					await new Promise(resolve => {
						entry.file(file => {
							if (supportedTypes.includes(file.type)) {
								files.push(file);
							}
							resolve();
						});
					});
				} else if (entry.isDirectory) {
					const reader = entry.createReader();
					await new Promise(resolve => {
						reader.readEntries(async entries => {
							await Promise.all(entries.map(e => readAllFilesFromEntry(e, files)));
							resolve();
						});
					});
				}
			}

			const btnClearAll = document.getElementById('start-btn-clear-all');
			if (btnClearAll) {
				btnClearAll.addEventListener('click', async function() {
					console.log('Clear all files requested from start page');
					await window.filesModel.clearFiles();
					
					// Update button states after clearing
					const btnStartProcess = document.getElementById('start-btn-start-process');
					const btnStopProcess = document.getElementById('start-btn-stop-process');
					if (btnStartProcess && btnStopProcess) {
						btnStartProcess.style.display = 'inline-block';
						btnStopProcess.style.display = 'none';
					}
					
					// Broadcast state change
					if (window.broadcastStateChange) {
						const outputFolderPath = document.getElementById('start-output-folder-path');
						const batchSizeInput = document.getElementById('start-batch-size-spinner');
						window.broadcastStateChange({
							outputFolder: outputFolderPath?.value?.trim() || '',
							batchSize: parseInt(batchSizeInput?.value, 10) || 5,
							isProcessing: false,
							showStopButton: false,
							filesClearedStop: true
						});
					}
					
					updateStartStats();
				});
			}

			setInterval(() => {
				updateStartStats();
			}, 2000);
		}

		function setupStartActions() {
			const outputFolderPath = document.getElementById('start-output-folder-path');
			const batchSizeInput = document.getElementById('start-batch-size-spinner');
			const btnStartProcess = document.getElementById('start-btn-start-process');
			const btnStopProcess = document.getElementById('start-btn-stop-process');
			
			if (!outputFolderPath || !batchSizeInput || !btnStartProcess || !btnStopProcess) {
				console.error('Missing required start action elements');
				return;
			}

			btnStartProcess.disabled = !outputFolderPath.value.trim();

			outputFolderPath.addEventListener('input', async function() {
				btnStartProcess.disabled = !outputFolderPath.value.trim();
				await window.appModel.setOutputFolder(outputFolderPath.value.trim());
				
				// Broadcast state change
				if (window.broadcastStateChange) {
					window.broadcastStateChange({
						outputFolder: outputFolderPath.value.trim(),
						batchSize: parseInt(batchSizeInput.value, 10) || 5,
						isProcessing: window.isProcessing,
						showStopButton: btnStopProcess.style.display !== 'none'
					});
				}
			});

			batchSizeInput.addEventListener('input', async function() {
				await window.appModel.setBatchSize(parseInt(batchSizeInput.value, 10) || 5);
				
				// Broadcast state change
				if (window.broadcastStateChange) {
					window.broadcastStateChange({
						outputFolder: outputFolderPath.value.trim(),
						batchSize: parseInt(batchSizeInput.value, 10) || 5,
						isProcessing: window.isProcessing,
						showStopButton: btnStopProcess.style.display !== 'none'
					});
				}
			});

			btnStartProcess.addEventListener('click', async function() {
				console.log('start process requested from start page');
				if (typeof openTabAndPrintUploadArea === 'function') {
					const outputFolder = outputFolderPath.value.trim();
					window.selectedOutputFolder = outputFolder;
					window.isProcessing = true;
					
					await window.appModel.setProcessingState(true);
					await window.appModel.setButtonState(true);
					
					btnStartProcess.style.display = 'none';
					btnStopProcess.style.display = 'inline-block';
					
					// Broadcast state change
					if (window.broadcastStateChange) {
						window.broadcastStateChange({
							outputFolder: outputFolder,
							batchSize: parseInt(batchSizeInput.value, 10) || 5,
							isProcessing: true,
							showStopButton: true
						});
					}
					
					openTabAndPrintUploadArea(outputFolder);
				}
			});

			btnStopProcess.addEventListener('click', async function() {
				console.log('stop process requested from start page');
				
				// Stop all processing tabs and set files to draft
				if (window.stopAllProcessingTabs) {
					await window.stopAllProcessingTabs();
				} else {
					// Fallback for when background workers not loaded
					window.isProcessing = false;
					window.shouldStopProcessing = true;
					
					await window.appModel.setProcessingState(false);
					await window.appModel.setButtonState(false);
					
					btnStartProcess.style.display = 'inline-block';
					btnStopProcess.style.display = 'none';
					
					// Broadcast state change
					if (window.broadcastStateChange) {
						window.broadcastStateChange({
							outputFolder: outputFolderPath.value.trim(),
							batchSize: parseInt(batchSizeInput.value, 10) || 5,
							isProcessing: false,
							showStopButton: false,
							shouldStopProcessing: true
						});
					}
				}
			});
		}

		async function restoreStartAppState() {
			try {
				const outputFolder = await window.appModel.getOutputFolder();
				const batchSize = await window.appModel.getBatchSize();
				const isProcessing = await window.appModel.getProcessingState();
				const showStopButton = await window.appModel.getButtonState();
				
				const outputFolderPath = document.getElementById('start-output-folder-path');
				if (outputFolderPath && outputFolder) {
					outputFolderPath.value = outputFolder;
				}
				
				const batchSizeInput = document.getElementById('start-batch-size-spinner');
				if (batchSizeInput && batchSize) {
					batchSizeInput.value = batchSize;
				} else if (batchSizeInput) {
					// Set default value if no saved batch size
					batchSizeInput.value = 5;
				}
				
				const btnStartProcess = document.getElementById('start-btn-start-process');
				const btnStopProcess = document.getElementById('start-btn-stop-process');
				if (btnStartProcess && btnStopProcess) {
					if (showStopButton) {
						btnStartProcess.style.display = 'none';
						btnStopProcess.style.display = 'inline-block';
						window.isProcessing = isProcessing;
					} else {
						btnStartProcess.style.display = 'inline-block';
						btnStopProcess.style.display = 'none';
						window.isProcessing = false;
						window.shouldStopProcessing = false;
					}
					
					btnStartProcess.disabled = !outputFolderPath?.value?.trim();
				}
				
				console.log('Start app state restored:', { outputFolder, batchSize, isProcessing, showStopButton });
				
				// Broadcast restored state for synchronization
				if (window.broadcastStateChange) {
					window.broadcastStateChange({
						outputFolder: outputFolder || '',
						batchSize: batchSize || 5,
						isProcessing: isProcessing || false,
						showStopButton: showStopButton || false
					});
				}
			} catch (error) {
				console.error('Failed to restore start app state:', error);
			}
		}

		async function updateStartStats() {
			const allFiles = await window.filesModel.getAllFiles();
			const totalFiles = allFiles.length;
			
			const draftCount = allFiles.filter(f => f.status === 'draft' || !f.status).length;
			const completedCount = allFiles.filter(f => f.status === 'completed').length;
			const failedCount = allFiles.filter(f => f.status === 'failed').length;
			const processingCount = allFiles.filter(f => f.status && f.status !== 'draft' && f.status !== 'completed' && f.status !== 'failed').length;
			
			const statsTotal = document.getElementById('start-stats-total');
			if (statsTotal) statsTotal.textContent = totalFiles;
			
			const statsDraftText = document.getElementById('start-stats-draft-text');
			const statsDraftProgress = document.getElementById('start-stats-draft-progress');
			if (statsDraftText) statsDraftText.textContent = `${draftCount}/${totalFiles}`;
			if (statsDraftProgress) {
				const draftPercentage = totalFiles > 0 ? (draftCount / totalFiles) * 100 : 0;
				statsDraftProgress.style.width = `${draftPercentage}%`;
			}
			
			const statsCompletedText = document.getElementById('start-stats-completed-text');
			const statsCompletedProgress = document.getElementById('start-stats-completed-progress');
			if (statsCompletedText) statsCompletedText.textContent = `${completedCount}/${totalFiles}`;
			if (statsCompletedProgress) {
				const completedPercentage = totalFiles > 0 ? (completedCount / totalFiles) * 100 : 0;
				statsCompletedProgress.style.width = `${completedPercentage}%`;
			}
			
			const statsFailedText = document.getElementById('start-stats-failed-text');
			const statsFailedProgress = document.getElementById('start-stats-failed-progress');
			if (statsFailedText) statsFailedText.textContent = `${failedCount}/${totalFiles}`;
			if (statsFailedProgress) {
				const failedPercentage = totalFiles > 0 ? (failedCount / totalFiles) * 100 : 0;
				statsFailedProgress.style.width = `${failedPercentage}%`;
			}
			
			const finishedCount = completedCount + failedCount;
			const overallProgressText = document.getElementById('start-overall-progress-text');
			const overallProgressBar = document.getElementById('start-overall-progress-bar');
			const overallProgressPercentage = document.getElementById('start-overall-progress-percentage');
			
			if (overallProgressText) overallProgressText.textContent = `${finishedCount}/${totalFiles}`;
			if (overallProgressBar && overallProgressPercentage) {
				const overallPercentage = totalFiles > 0 ? (finishedCount / totalFiles) * 100 : 0;
				overallProgressBar.style.width = `${overallPercentage}%`;
				overallProgressPercentage.textContent = `${Math.round(overallPercentage)}%`;
				
				if (window.isProcessing && finishedCount < totalFiles) {
					overallProgressBar.classList.add('progress-bar-animated');
				} else {
					overallProgressBar.classList.remove('progress-bar-animated');
					
					// Check if processing is complete and reset button state
					if (window.isProcessing && totalFiles > 0 && finishedCount >= totalFiles) {
						console.log('All files processed, resetting button state');
						window.isProcessing = false;
						window.shouldStopProcessing = false;
						
						// Update database state
						await window.appModel.setProcessingState(false);
						await window.appModel.setButtonState(false);
						
						// Reset start page buttons
						const startBtnStartProcess = document.getElementById('start-btn-start-process');
						const startBtnStopProcess = document.getElementById('start-btn-stop-process');
						if (startBtnStartProcess && startBtnStopProcess) {
							startBtnStartProcess.style.display = 'inline-block';
							startBtnStopProcess.style.display = 'none';
						}
						
						// Reset program page buttons if they exist
						const btnStartProcess = document.getElementById('btn-start-process');
						const btnStopProcess = document.getElementById('btn-stop-process');
						if (btnStartProcess && btnStopProcess) {
							btnStartProcess.style.display = 'inline-block';
							btnStopProcess.style.display = 'none';
						}
						
						// Broadcast state change
						if (window.broadcastStateChange) {
							const outputPath = document.getElementById('start-output-folder-path');
							const batchSize = document.getElementById('start-batch-size-spinner');
							window.broadcastStateChange({
								outputFolder: outputPath?.value?.trim() || '',
								batchSize: parseInt(batchSize?.value, 10) || 5,
								isProcessing: false,
								showStopButton: false,
								resetComplete: true
							});
						}
					}
				}
			}
		}
	}

	// Cross-page synchronization system
	function initializeCrossPageSync() {
		// Listen for storage changes to sync across pages
		window.addEventListener('storage', function(e) {
			if (e.key === 'sotong_sync_state') {
				const syncData = JSON.parse(e.newValue || '{}');
				handleSyncStateChange(syncData);
			}
		});

		// Listen for custom events within the same page
		window.addEventListener('sotong_state_change', function(e) {
			const syncData = e.detail;
			handleSyncStateChange(syncData);
		});
	}

	function handleSyncStateChange(syncData) {
		if (!syncData) return;

		console.log('Handling sync state change:', syncData);

		// Update start page elements if they exist
		const startBtnStartProcess = document.getElementById('start-btn-start-process');
		const startBtnStopProcess = document.getElementById('start-btn-stop-process');
		const startOutputPath = document.getElementById('start-output-folder-path');
		const startBatchSize = document.getElementById('start-batch-size-spinner');

		if (startBtnStartProcess && startBtnStopProcess) {
			console.log('Updating start page buttons:', { showStopButton: syncData.showStopButton });
			if (syncData.showStopButton) {
				startBtnStartProcess.style.display = 'none';
				startBtnStopProcess.style.display = 'block';
			} else {
				startBtnStartProcess.style.display = 'block';
				startBtnStopProcess.style.display = 'none';
			}
			startBtnStartProcess.disabled = !syncData.outputFolder?.trim();
		}

		if (startOutputPath && syncData.outputFolder !== undefined) {
			if (startOutputPath.value !== syncData.outputFolder) {
				startOutputPath.value = syncData.outputFolder;
			}
		}

		if (startBatchSize && syncData.batchSize !== undefined) {
			if (parseInt(startBatchSize.value, 10) !== syncData.batchSize) {
				startBatchSize.value = syncData.batchSize;
			}
		} else if (startBatchSize && syncData.batchSize === undefined) {
			// Ensure default value if not set
			if (!startBatchSize.value || startBatchSize.value === '0') {
				startBatchSize.value = 5;
			}
		}

		// Update program page elements if they exist
		const btnStartProcess = document.getElementById('btn-start-process');
		const btnStopProcess = document.getElementById('btn-stop-process');
		const outputPath = document.getElementById('output-folder-path');
		const batchSize = document.getElementById('batch-size-spinner');

		if (btnStartProcess && btnStopProcess) {
			console.log('Updating program page buttons:', { showStopButton: syncData.showStopButton });
			if (syncData.showStopButton) {
				btnStartProcess.style.display = 'none';
				btnStopProcess.style.display = 'block';
			} else {
				btnStartProcess.style.display = 'block';
				btnStopProcess.style.display = 'none';
			}
			btnStartProcess.disabled = !syncData.outputFolder?.trim();
		}

		if (outputPath && syncData.outputFolder !== undefined) {
			if (outputPath.value !== syncData.outputFolder) {
				outputPath.value = syncData.outputFolder;
			}
		}

		if (batchSize && syncData.batchSize !== undefined) {
			if (parseInt(batchSize.value, 10) !== syncData.batchSize) {
				batchSize.value = syncData.batchSize;
			}
		}

		// Update global state
		if (syncData.isProcessing !== undefined) {
			window.isProcessing = syncData.isProcessing;
		}
		if (syncData.shouldStopProcessing !== undefined) {
			window.shouldStopProcessing = syncData.shouldStopProcessing;
		}
	}

	function broadcastStateChange(syncData) {
		console.log('Broadcasting state change:', syncData);
		
		// Store in localStorage for cross-tab communication
		localStorage.setItem('sotong_sync_state', JSON.stringify({
			...syncData,
			timestamp: Date.now()
		}));
		
		// Dispatch custom event for same-page communication
		window.dispatchEvent(new CustomEvent('sotong_state_change', { detail: syncData }));
	}

	// Periodic sync check to ensure pages stay synchronized
	function periodicSyncCheck() {
		const syncData = localStorage.getItem('sotong_sync_state');
		if (syncData) {
			try {
				const data = JSON.parse(syncData);
				// Only process if the data is recent (within last 30 seconds)
				if (Date.now() - (data.timestamp || 0) < 30000) {
					handleSyncStateChange(data);
				}
			} catch (e) {
				console.error('Error parsing sync data:', e);
			}
		}
	}

	// Make sync functions available globally
	window.broadcastStateChange = broadcastStateChange;
	window.handleSyncStateChange = handleSyncStateChange;

	// Initialize synchronization
	initializeCrossPageSync();
	
	// Start periodic sync check every 2 seconds
	setInterval(periodicSyncCheck, 2000);
});