/* Persist only a user-granted directory handle, scoped to this checkout's URL. */
(() => {
  'use strict';

  async function access(mode, operation) {
    const db = await new Promise((resolve, reject) => {
      const request = indexedDB.open('application-filler-folders', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('folders');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error('Browser storage is unavailable.'));
    });
    try {
      return await new Promise((resolve, reject) => {
        const transaction = db.transaction('folders', mode);
        const request = operation(transaction.objectStore('folders'));
        transaction.oncomplete = () => resolve(request.result);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error || new Error('Browser storage was interrupted.'));
      });
    } finally { db.close(); }
  }

  window.CONFIG_FOLDER_STORE = {
    load: (key) => access('readonly', (store) => store.get(key)),
    save: (key, handle) => access('readwrite', (store) => store.put(handle, key))
  };
})();
