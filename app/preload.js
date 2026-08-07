const { contextBridge } = require('electron');
contextBridge.exposeInMainWorld('pakon', { platform: process.platform, packaged: true });
