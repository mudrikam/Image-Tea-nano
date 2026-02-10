document.addEventListener('DOMContentLoaded', function() {
  const appRoot = document.getElementById('app-root');
  if (!appRoot) return;

  // Load models first
  const loadModels = async () => {
    await Promise.all([
      new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'models/files_model.js';
        script.onload = resolve;
        document.head.appendChild(script);
      }),
      new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = 'models/app_model.js';
        script.onload = resolve;
        document.head.appendChild(script);
      })
    ]);
  };

  loadModels().then(() => {
    Promise.all([
      fetch('widgets/actions.html').then(response => response.text()),
      fetch('widgets/stats.html').then(response => response.text()),
      fetch('widgets/dnd_area.html').then(response => response.text()),
      fetch('widgets/main_table.html').then(response => response.text())
    ]).then(([actionsHtml, statsHtml, dndHtml, tableHtml]) => {
      appRoot.innerHTML = actionsHtml + statsHtml + dndHtml + tableHtml;
      setupDndArea();
      setupActions();
      updateStats();
      restoreAppState();
    });
  });

  function setupDndArea() {
    const dropzone = document.getElementById('dnd-dropzone');
    const fileInput = document.getElementById('dnd-file-input');
    const folderInput = document.getElementById('dnd-folder-input');
    const btnSelectFiles = document.getElementById('btn-select-files');
    const btnSelectFolder = document.getElementById('btn-select-folder');
    const fileTableBody = document.querySelector('#main-file-table tbody');
    const searchInput = document.getElementById('file-table-search');
    const pagination = document.getElementById('file-table-pagination');
    const tableHeaders = document.querySelectorAll('#main-file-table th.sortable');
    const pageSizeSelect = document.getElementById('file-table-pagesize');
    const supportedTypes = [
      'image/jpeg',
      'image/png',
      'image/webp',
      'image/heic'
    ];


    let allFiles = [];
    let filteredFiles = [];
    let currentPage = 1;
    let pageSize = parseInt(pageSizeSelect.value, 10);
    let sortAsc = true;
    let fileLoadingCancelled = false;

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
        // Show modal for folder scanning
        showFileLoadingModal();
        updateFileLoadingProgress(0, 1, 'Scanning folders...');
        
        const entries = [];
        for (let i = 0; i < items.length; i++) {
          const entry = items[i].webkitGetAsEntry();
          if (entry) entries.push(entry);
        }
        await Promise.all(entries.map(entry => readAllFilesFromEntry(entry, files)));
      } else {
        files = Array.from(e.dataTransfer.files);
      }
      await setFiles(files);
    });

    fileInput.addEventListener('change', async function(e) {
      await setFiles(Array.from(e.target.files));
    });

    folderInput.addEventListener('change', async function(e) {
      const files = Array.from(e.target.files);
      if (files.length > 10) {
        showFileLoadingModal();
        updateFileLoadingProgress(0, files.length, 'Preparing files...');
      }
      await setFiles(files);
    });

    searchInput.addEventListener('input', function() {
      currentPage = 1;
      updateTable();
    });

    pageSizeSelect.addEventListener('change', function() {
      pageSize = parseInt(pageSizeSelect.value, 10);
      currentPage = 1;
      updateTable();
    });

    tableHeaders.forEach(header => {
      header.addEventListener('click', function() {
        sortAsc = !sortAsc;
        updateTable();
        updateSortIcons();
      });
    });

    async function setFiles(files) {
      if (!files || files.length === 0) return;
      
      // Show loading modal if there are many files
      if (files.length > 10) {
        showFileLoadingModal();
      }
      
      // Filter only files with valid name and avoid duplicates
      const existingFiles = await window.filesModel.getAllFiles();
      const existingNames = new Set(existingFiles.map(f => f.name));
      const newFiles = files.filter(f => f.name && !existingNames.has(f.name));
      
      if (newFiles.length > 0) {
        if (newFiles.length > 10) {
          // Process files in chunks with progress updates
          await processFilesWithProgress(newFiles);
        } else {
          await window.filesModel.addFiles(newFiles);
        }
      }
      
      // Hide loading modal
      hideFileLoadingModal();
      
      await refreshFiles();
    }

    function showFileLoadingModal() {
      fileLoadingCancelled = false;
      const modal = document.getElementById('file-loading-modal');
      const cancelBtn = document.getElementById('btn-cancel-file-loading');
      
      if (cancelBtn) {
        cancelBtn.onclick = function() {
          fileLoadingCancelled = true;
          hideFileLoadingModal();
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

    function hideFileLoadingModal() {
      const modal = document.getElementById('file-loading-modal');
      if (modal) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          const bootstrapModal = bootstrap.Modal.getInstance(modal);
          if (bootstrapModal) {
            bootstrapModal.hide();
          }
        } else {
          // Fallback: hide modal without bootstrap
          modal.style.display = 'none';
          modal.classList.remove('show');
        }
      }
    }

    function updateFileLoadingProgress(current, total, fileName = '') {
      const progressText = document.getElementById('file-progress-text');
      const progressBar = document.getElementById('file-progress-bar');
      const progressPercentage = document.getElementById('file-progress-percentage');
      const currentFileInfo = document.getElementById('current-file-info');
      
      if (progressText) progressText.textContent = `${current}/${total} files`;
      
      const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
      if (progressBar) progressBar.style.width = `${percentage}%`;
      if (progressPercentage) progressPercentage.textContent = `${percentage}%`;
      
      if (currentFileInfo && fileName) {
        currentFileInfo.textContent = `Processing: ${fileName}`;
      }
    }

    async function processFilesWithProgress(files) {
      const chunkSize = 5;
      let processed = 0;
      
      for (let i = 0; i < files.length; i += chunkSize) {
        if (fileLoadingCancelled) {
          console.log('File loading cancelled by user');
          break;
        }
        
        const chunk = files.slice(i, i + chunkSize);
        
        for (const file of chunk) {
          if (fileLoadingCancelled) break;
          
          updateFileLoadingProgress(processed + 1, files.length, file.name);
          processed++;
          
          await new Promise(resolve => setTimeout(resolve, 10));
        }
        
        if (!fileLoadingCancelled) {
          await window.filesModel.addFiles(chunk);
        }
        
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      if (!fileLoadingCancelled) {
        updateFileLoadingProgress(files.length, files.length, 'Complete!');
      }
    }

    async function refreshFiles() {
      const query = searchInput.value.trim().toLowerCase();
      allFiles = await window.filesModel.getAllFiles();
      filteredFiles = allFiles.filter(file => file.name.toLowerCase().includes(query));
      filteredFiles.sort((a, b) => {
        let valA = a.name.toLowerCase();
        let valB = b.name.toLowerCase();
        if (valA < valB) return sortAsc ? -1 : 1;
        if (valA > valB) return sortAsc ? 1 : -1;
        return 0;
      });
      const totalPages = Math.max(1, Math.ceil(filteredFiles.length / pageSize));
      if (currentPage > totalPages) currentPage = totalPages;
      const startIdx = (currentPage - 1) * pageSize;
      const endIdx = startIdx + pageSize;
      const pageFiles = filteredFiles.slice(startIdx, endIdx);

      fileTableBody.innerHTML = '';
      for (const file of pageFiles) {
        const row = document.createElement('tr');
        const nameCell = document.createElement('td');
        nameCell.textContent = file.name;
        row.appendChild(nameCell);

        // Status column (from db) with progress bar
        const statusCell = document.createElement('td');
        if (!file.status || file.status === 'draft') {
          const badge = document.createElement('span');
          badge.className = 'badge bg-secondary';
          badge.textContent = 'draft';
          statusCell.appendChild(badge);
        } else if (file.status === 'completed') {
          const badge = document.createElement('span');
          badge.className = 'badge bg-success';
          badge.textContent = 'completed';
          statusCell.appendChild(badge);
        } else if (file.status === 'failed') {
          const badge = document.createElement('span');
          badge.className = 'badge bg-danger';
          badge.textContent = 'failed';
          statusCell.appendChild(badge);
        } else if (file.status && file.progress !== undefined && file.progress > 0) {
          // Progress bar for active processing
          const progressContainer = document.createElement('div');
          progressContainer.style.width = '100%';
          
          const progressBar = document.createElement('div');
          progressBar.className = 'progress';
          progressBar.style.height = '20px';
          
          const progressFill = document.createElement('div');
          progressFill.className = 'progress-bar';
          progressFill.style.width = `${file.progress}%`;
          progressFill.setAttribute('aria-valuenow', file.progress);
          progressFill.setAttribute('aria-valuemin', '0');
          progressFill.setAttribute('aria-valuemax', '100');
          
          // Color based on progress stage
          if (file.progress < 25) {
            progressFill.className += ' bg-danger'; // Opening tab - red
          } else if (file.progress < 50) {
            progressFill.className += ' bg-warning'; // Loading/uploading - yellow
          } else if (file.progress < 75) {
            progressFill.className += ' bg-info'; // Processing - blue
          } else {
            progressFill.className += ' bg-success'; // Nearly done - green
          }
          
          progressBar.appendChild(progressFill);
          
          const statusText = document.createElement('small');
          statusText.className = 'd-block mt-1 text-muted';
          statusText.textContent = file.status;
          
          progressContainer.appendChild(progressBar);
          progressContainer.appendChild(statusText);
          statusCell.appendChild(progressContainer);
        } else {
          // For other statuses, show as text
          const statusText = document.createElement('span');
          statusText.className = 'text-muted';
          statusText.textContent = file.status || 'unknown';
          statusCell.appendChild(statusText);
        }
        row.appendChild(statusCell);

        // Actions column
        const actionsCell = document.createElement('td');
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-sm btn-danger';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', async function() {
          await window.filesModel.deleteFile(file.name);
          await refreshFiles();
        });
        actionsCell.appendChild(deleteBtn);
        row.appendChild(actionsCell);

        fileTableBody.appendChild(row);
      }
      renderPagination(totalPages);
    }

    function renderPagination(totalPages) {
      pagination.innerHTML = '';
      if (totalPages <= 1) return;
      const maxDisplay = 5;
      const createPageItem = (page, active = false, disabled = false, text = null) => {
        const li = document.createElement('li');
        li.className = 'page-item' + (active ? ' active' : '') + (disabled ? ' disabled' : '');
        const a = document.createElement('a');
        a.className = 'page-link';
        a.href = '#';
        a.textContent = text !== null ? text : page;
        if (!disabled) {
          a.addEventListener('click', function(e) {
            e.preventDefault();
            currentPage = page;
            updateTable();
          });
        }
        li.appendChild(a);
        return li;
      };
      if (currentPage > 1) {
        pagination.appendChild(createPageItem(currentPage - 1, false, false, '«'));
      }
      let startPage = 1;
      let endPage = totalPages;
      if (totalPages > maxDisplay) {
        if (currentPage <= 3) {
          startPage = 1;
          endPage = maxDisplay;
        } else if (currentPage >= totalPages - 2) {
          startPage = totalPages - maxDisplay + 1;
          endPage = totalPages;
        } else {
          startPage = currentPage - 2;
          endPage = currentPage + 2;
        }
      }
      if (startPage > 1) {
        pagination.appendChild(createPageItem(1));
        if (startPage > 2) {
          const li = document.createElement('li');
          li.className = 'page-item disabled';
          li.innerHTML = '<span class="page-link">...</span>';
          pagination.appendChild(li);
        }
      }
      for (let i = startPage; i <= endPage; i++) {
        if (i > 0 && i <= totalPages) {
          pagination.appendChild(createPageItem(i, i === currentPage));
        }
      }
      if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
          const li = document.createElement('li');
          li.className = 'page-item disabled';
          li.innerHTML = '<span class="page-link">...</span>';
          pagination.appendChild(li);
        }
        pagination.appendChild(createPageItem(totalPages));
      }
      if (currentPage < totalPages) {
        pagination.appendChild(createPageItem(currentPage + 1, false, false, '»'));
      }
    }

    function updateTable() {
      refreshFiles();
    }

    function updateSortIcons() {
      tableHeaders.forEach(header => {
        const icon = header.querySelector('span');
        icon.className = 'fa ' + (sortAsc ? 'fa-sort-alpha-down' : 'fa-sort-alpha-up');
      });
    }

    async function readAllFilesFromEntry(entry, files) {
      if (entry.isFile) {
        await new Promise(resolve => {
          entry.file(file => {
            files.push(file);
            // Update progress during folder scanning
            const currentFileInfo = document.getElementById('current-file-info');
            if (currentFileInfo) {
              currentFileInfo.textContent = `Found: ${file.name} (${files.length} files total)`;
            }
            resolve();
          });
        });
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        await new Promise(resolve => {
          function readEntries() {
            reader.readEntries(async entries => {
              if (entries.length === 0) {
                resolve();
                return;
              }
              
              // Update progress for directory scanning
              const currentFileInfo = document.getElementById('current-file-info');
              if (currentFileInfo) {
                currentFileInfo.textContent = `Scanning folder: ${entry.name}`;
              }
              
              for (const ent of entries) {
                await readAllFilesFromEntry(ent, files);
              }
              readEntries();
            });
          }
          readEntries();
        });
      }
    }

    // Clear All button handler
    const btnClearAll = document.getElementById('btn-clear-all');
    if (btnClearAll) {
      btnClearAll.addEventListener('click', async function() {
        console.log('Clear all files requested from program page');
        await window.filesModel.clearFiles();
        
        // Update button states after clearing
        const btnStartProcess = document.getElementById('btn-start-process');
        const btnStopProcess = document.getElementById('btn-stop-process');
        if (btnStartProcess && btnStopProcess) {
          btnStartProcess.style.display = 'inline-block';
          btnStopProcess.style.display = 'none';
        }
        
        // Broadcast state change
        if (window.broadcastStateChange) {
          const outputFolderPath = document.getElementById('output-folder-path');
          const batchSizeInput = document.getElementById('batch-size-spinner');
          window.broadcastStateChange({
            outputFolder: outputFolderPath?.value?.trim() || '',
            batchSize: parseInt(batchSizeInput?.value, 10) || 5,
            isProcessing: false,
            showStopButton: false,
            filesClearedStop: true
          });
        }
        
        await refreshFiles();
      });
    }

    // Initial load and setup auto-refresh
    refreshFiles();
    
    // Auto-refresh table every 2 seconds during processing
    setInterval(() => {
      refreshFiles();
      updateStats();
    }, 2000);
  }

  function setupActions() {
    const outputFolderPath = document.getElementById('output-folder-path');
    const batchSizeInput = document.getElementById('batch-size-spinner');
    const btnStartProcess = document.getElementById('btn-start-process');
    const btnStopProcess = document.getElementById('btn-stop-process');
    
    console.log('Button elements found:', {
      outputFolderPath: !!outputFolderPath,
      batchSizeInput: !!batchSizeInput,
      btnStartProcess: !!btnStartProcess,
      btnStopProcess: !!btnStopProcess
    });
    
    if (!outputFolderPath || !batchSizeInput || !btnStartProcess || !btnStopProcess) {
      console.error('Missing required button elements');
      return;
    }

    // Initial state
    btnStartProcess.disabled = !outputFolderPath.value.trim();

    // Save output folder on change
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

    // Save batch size on change
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

    // Call background worker to open tab and check uploadArea when Start Process is clicked
    btnStartProcess.addEventListener('click', async function() {
      console.log('start process requested');
      if (typeof openTabAndPrintUploadArea === 'function') {
        const outputFolder = outputFolderPath.value.trim();
        window.selectedOutputFolder = outputFolder;
        window.isProcessing = true;
        
        // Save processing state
        await window.appModel.setProcessingState(true);
        await window.appModel.setButtonState(true);
        
        // Switch buttons immediately
        console.log('Switching to stop button');
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
        
        // Start processing
        openTabAndPrintUploadArea(outputFolder);
      }
    });

    // Stop processing when Stop Process is clicked
    btnStopProcess.addEventListener('click', async function() {
      console.log('stop process requested');
      
      // Stop all processing tabs and set files to draft
      if (window.stopAllProcessingTabs) {
        await window.stopAllProcessingTabs();
      } else {
        // Fallback for when background workers not loaded
        window.isProcessing = false;
        window.shouldStopProcessing = true;
        
        // Save processing state
        await window.appModel.setProcessingState(false);
        await window.appModel.setButtonState(false);
        
        // Switch buttons back immediately
        console.log('Switching to start button');
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

  // Function to restore app state from persistence
  async function restoreAppState() {
    try {
      const outputFolder = await window.appModel.getOutputFolder();
      const batchSize = await window.appModel.getBatchSize();
      const isProcessing = await window.appModel.getProcessingState();
      const showStopButton = await window.appModel.getButtonState();
      
      // Restore output folder
      const outputFolderPath = document.getElementById('output-folder-path');
      if (outputFolderPath && outputFolder) {
        outputFolderPath.value = outputFolder;
      }
      
      // Restore batch size
      const batchSizeInput = document.getElementById('batch-size-spinner');
      if (batchSizeInput && batchSize) {
        batchSizeInput.value = batchSize;
      }
      
      // Restore button state
      const btnStartProcess = document.getElementById('btn-start-process');
      const btnStopProcess = document.getElementById('btn-stop-process');
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
        
        // Update button disabled state
        btnStartProcess.disabled = !outputFolderPath?.value?.trim();
      }
      
      console.log('App state restored:', { outputFolder, batchSize, isProcessing, showStopButton });
      
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
      console.error('Failed to restore app state:', error);
    }
  }

  // Function to update statistics
  async function updateStats() {
    const allFiles = await window.filesModel.getAllFiles();
    const totalFiles = allFiles.length;
    
    // Count by status
    const draftCount = allFiles.filter(f => f.status === 'draft' || !f.status).length;
    const completedCount = allFiles.filter(f => f.status === 'completed').length;
    const failedCount = allFiles.filter(f => f.status === 'failed').length;
    const processingCount = allFiles.filter(f => f.status && f.status !== 'draft' && f.status !== 'completed' && f.status !== 'failed').length;
    
    // Update total files
    const statsTotal = document.getElementById('stats-total');
    if (statsTotal) statsTotal.textContent = totalFiles;
    
    // Update draft stats
    const statsDraftText = document.getElementById('stats-draft-text');
    const statsDraftProgress = document.getElementById('stats-draft-progress');
    if (statsDraftText) statsDraftText.textContent = `${draftCount}/${totalFiles}`;
    if (statsDraftProgress) {
      const draftPercentage = totalFiles > 0 ? (draftCount / totalFiles) * 100 : 0;
      statsDraftProgress.style.width = `${draftPercentage}%`;
    }
    
    // Update completed stats
    const statsCompletedText = document.getElementById('stats-completed-text');
    const statsCompletedProgress = document.getElementById('stats-completed-progress');
    if (statsCompletedText) statsCompletedText.textContent = `${completedCount}/${totalFiles}`;
    if (statsCompletedProgress) {
      const completedPercentage = totalFiles > 0 ? (completedCount / totalFiles) * 100 : 0;
      statsCompletedProgress.style.width = `${completedPercentage}%`;
    }
    
    // Update failed stats
    const statsFailedText = document.getElementById('stats-failed-text');
    const statsFailedProgress = document.getElementById('stats-failed-progress');
    if (statsFailedText) statsFailedText.textContent = `${failedCount}/${totalFiles}`;
    if (statsFailedProgress) {
      const failedPercentage = totalFiles > 0 ? (failedCount / totalFiles) * 100 : 0;
      statsFailedProgress.style.width = `${failedPercentage}%`;
    }
    
    // Update overall progress
    const finishedCount = completedCount + failedCount;
    const overallProgressText = document.getElementById('overall-progress-text');
    const overallProgressBar = document.getElementById('overall-progress-bar');
    const overallProgressPercentage = document.getElementById('overall-progress-percentage');
    
    if (overallProgressText) overallProgressText.textContent = `${finishedCount}/${totalFiles}`;
    if (overallProgressBar && overallProgressPercentage) {
      const overallPercentage = totalFiles > 0 ? (finishedCount / totalFiles) * 100 : 0;
      overallProgressBar.style.width = `${overallPercentage}%`;
      overallProgressPercentage.textContent = `${Math.round(overallPercentage)}%`;
      
      // Add animation when processing
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
          
          // Reset program page buttons
          const btnStartProcess = document.getElementById('btn-start-process');
          const btnStopProcess = document.getElementById('btn-stop-process');
          if (btnStartProcess && btnStopProcess) {
            btnStartProcess.style.display = 'inline-block';
            btnStopProcess.style.display = 'none';
          }
          
          // Reset start page buttons if they exist
          const startBtnStartProcess = document.getElementById('start-btn-start-process');
          const startBtnStopProcess = document.getElementById('start-btn-stop-process');
          if (startBtnStartProcess && startBtnStopProcess) {
            startBtnStartProcess.style.display = 'inline-block';
            startBtnStopProcess.style.display = 'none';
          }
          
          // Broadcast state change
          if (window.broadcastStateChange) {
            const outputPath = document.getElementById('output-folder-path');
            const batchSize = document.getElementById('batch-size-spinner');
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
});
