if (!window.AppModel) {
    class AppModel {
        constructor(dbName = 'SotongHDLiteApp', storeName = 'settings') {
            this.dbName = dbName;
            this.storeName = storeName;
            this.db = null;
            this.defaultSettings = {
                outputFolder: '',
                batchSize: 5,
                isProcessing: false,
                showStopButton: false
            };
        }

    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, 1);
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(this.storeName)) {
                    const store = db.createObjectStore(this.storeName, { keyPath: 'key' });
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

    async getSetting(key) {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction([this.storeName], 'readonly');
            const store = tx.objectStore(this.storeName);
            const request = store.get(key);
            request.onsuccess = (event) => {
                const result = event.target.result;
                if (result) {
                    resolve(result.value);
                } else {
                    resolve(this.defaultSettings[key] || null);
                }
            };
            request.onerror = (event) => {
                reject(event.target.error);
            };
        });
    }

    async setSetting(key, value) {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction([this.storeName], 'readwrite');
            const store = tx.objectStore(this.storeName);
            const request = store.put({
                key: key,
                value: value,
                lastUpdated: new Date().toISOString()
            });
            request.onsuccess = () => resolve();
            request.onerror = (event) => reject(event.target.error);
        });
    }

    async getAllSettings() {
        if (!this.db) await this.init();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction([this.storeName], 'readonly');
            const store = tx.objectStore(this.storeName);
            const request = store.getAll();
            request.onsuccess = (event) => {
                const results = event.target.result;
                const settings = { ...this.defaultSettings };
                results.forEach(item => {
                    settings[item.key] = item.value;
                });
                resolve(settings);
            };
            request.onerror = (event) => {
                reject(event.target.error);
            };
        });
    }

    // Convenience methods for specific settings
    async getOutputFolder() {
        return await this.getSetting('outputFolder');
    }

    async setOutputFolder(folder) {
        return await this.setSetting('outputFolder', folder);
    }

    async getBatchSize() {
        return await this.getSetting('batchSize');
    }

    async setBatchSize(size) {
        return await this.setSetting('batchSize', size);
    }

    async getProcessingState() {
        return await this.getSetting('isProcessing');
    }

    async setProcessingState(isProcessing) {
        return await this.setSetting('isProcessing', isProcessing);
    }

    async getButtonState() {
        return await this.getSetting('showStopButton');
    }

    async setButtonState(showStopButton) {
        return await this.setSetting('showStopButton', showStopButton);
    }
}

window.AppModel = AppModel;
}

if (!window.appModel) {
    window.appModel = new AppModel();
}
