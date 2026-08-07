const { contextBridge } = require('electron');
contextBridge.exposeInMainWorld('pakon', {
  platform: process.platform,
  shell: 'electron',
});
