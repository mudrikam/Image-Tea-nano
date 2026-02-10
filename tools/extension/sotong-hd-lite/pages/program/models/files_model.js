if (!window.FilesModel) {
	class FilesModel {
		constructor(dbName = 'SotongHDLiteFiles', storeName = 'files') {
			this.dbName = dbName;
			this.storeName = storeName;
			this.db = null;
		}

		async init() {
			return new Promise((resolve, reject) => {
				const request = indexedDB.open(this.dbName, 1);
			request.onupgradeneeded = (event) => {
				const db = event.target.result;
				if (!db.objectStoreNames.contains(this.storeName)) {
					db.createObjectStore(this.storeName, { keyPath: 'name' });
				}
			};
			request.onsuccess = (event) => {
				this.db = event.target.result;
				resolve();
			};
			request.onerror = (event) => {
				reject(event.target.error);
			};
		});
	}

	async addFiles(files) {
		if (!this.db) await this.init();
		return new Promise((resolve, reject) => {
			let processed = 0;
			for (const file of files) {
				const reader = new FileReader();
				reader.onload = (e) => {
					const tx = this.db.transaction([this.storeName], 'readwrite');
					const store = tx.objectStore(this.storeName);
					store.put({
						name: file.name,
						status: 'draft',
						data: e.target.result,
						type: file.type || 'image/png'
					});
					tx.oncomplete = () => {
						processed++;
						if (processed === files.length) {
							resolve();
						}
					};
					tx.onerror = (event) => {
						reject(event.target.error);
					};
				};
				reader.onerror = (event) => {
					reject(event.target.error);
				};
				reader.readAsDataURL(file);
			}
		});
	}

	async getAllFiles() {
		if (!this.db) await this.init();
		return new Promise((resolve, reject) => {
			const tx = this.db.transaction([this.storeName], 'readonly');
			const store = tx.objectStore(this.storeName);
			const request = store.getAll();
			request.onsuccess = (event) => {
				resolve(event.target.result);
			};
			request.onerror = (event) => {
				reject(event.target.error);
			};
		});
	}

	async clearFiles() {
		// Stop all processing tabs first
		if (window.stopAllProcessingTabs) {
			await window.stopAllProcessingTabs();
		}
		
		// Set any stuck/processing files to failed before clearing
		await this.setStuckFilesToFailed();
		
		// Set processing state to false
		if (window.appModel) {
			await window.appModel.setProcessingState(false);
			await window.appModel.setButtonState(false);
		}
		
		// Clear all files from database
		if (!this.db) await this.init();
		return new Promise((resolve, reject) => {
			const tx = this.db.transaction([this.storeName], 'readwrite');
			const store = tx.objectStore(this.storeName);
			const request = store.clear();
			request.onsuccess = () => resolve();
			request.onerror = (event) => reject(event.target.error);
		});
	}

	async setStuckFilesToFailed() {
		if (!this.db) await this.init();
		
		const files = await this.getAllFiles();
		const stuckFiles = files.filter(file => 
			file.status && 
			file.status !== 'draft' && 
			file.status !== 'completed' && 
			file.status !== 'failed' &&
			typeof file.status === 'string' &&
			(file.status.includes('...') || 
			 file.status.includes('Processing') || 
			 file.status.includes('Uploading') || 
			 file.status.includes('Finding') ||
			 file.status.includes('Downloading') ||
			 file.status.includes('Tab') ||
			 file.status.includes('Opening'))
		);
		
		console.log(`Setting ${stuckFiles.length} stuck files to failed status`);
		
		for (const file of stuckFiles) {
			await this.updateFileStatus(file.name, 'failed', 0);
		}
		
		return stuckFiles.length;
	}

	async deleteFile(name) {
			if (!this.db) await this.init();
			return new Promise((resolve, reject) => {
				const tx = this.db.transaction([this.storeName], 'readwrite');
				const store = tx.objectStore(this.storeName);
				const request = store.delete(name);
				request.onsuccess = () => resolve();
				request.onerror = (event) => reject(event.target.error);
			});
		}

		async updateFileStatus(name, status, progress = 0) {
			if (!this.db) await this.init();
			return new Promise((resolve, reject) => {
				const tx = this.db.transaction([this.storeName], 'readwrite');
				const store = tx.objectStore(this.storeName);
				const request = store.get(name);
				request.onsuccess = (event) => {
					const file = event.target.result;
					if (file) {
						file.status = status;
						file.progress = progress;
						file.lastUpdated = new Date().toISOString();
						store.put(file);
					}
					resolve();
				};
				request.onerror = (event) => reject(event.target.error);
			});
		}
	}

	window.FilesModel = FilesModel;
}

if (!window.filesModel) {
	window.filesModel = new FilesModel();
}
