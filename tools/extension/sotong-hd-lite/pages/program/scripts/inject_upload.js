// Content script: inject_upload.js
chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
    if (message.type === 'upload-image' && message.fileData && message.fileName) {
        const uploadArea = document.getElementById('uploadArea');
        if (!uploadArea) {
            console.log('inject_upload.js: uploadArea not found');
            sendResponse({ success: false, reason: 'uploadArea not found' });
            return;
        }
        // Create a File object from base64 data
        function base64ToBlob(base64, mime) {
            const byteString = atob(base64.split(',')[1]);
            const ab = new ArrayBuffer(byteString.length);
            const ia = new Uint8Array(ab);
            for (let i = 0; i < byteString.length; i++) {
                ia[i] = byteString.charCodeAt(i);
            }
            return new Blob([ab], { type: mime });
        }
        const mimeType = message.fileType || 'image/png';
        const blob = base64ToBlob(message.fileData, mimeType);
        const file = new File([blob], message.fileName, { type: mimeType });
        // Find file input inside uploadArea
        let input = uploadArea.querySelector('input[type="file"]');
        if (!input) {
            input = document.createElement('input');
            input.type = 'file';
            input.style.display = 'none';
            uploadArea.appendChild(input);
        }
        // Create DataTransfer and set file
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        // Dispatch change event
        input.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('inject_upload.js: file dropped to uploadArea');
        sendResponse({ success: true });
    }
    return true;
});
