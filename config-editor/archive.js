/* Small, uncompressed ZIP export for browsers without direct folder access. */
(() => {
  'use strict';

  const crcTable = Uint32Array.from({ length: 256 }, (_, byte) => {
    let value = byte;
    for (let bit = 0; bit < 8; bit += 1) value = (value >>> 1) ^ ((value & 1) ? 0xedb88320 : 0);
    return value >>> 0;
  });

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) crc = (crc >>> 8) ^ crcTable[(crc ^ byte) & 0xff];
    return (crc ^ 0xffffffff) >>> 0;
  }

  window.createSetupArchive = async (source, cvFile, transcriptFile = null) => {
    const encoder = new TextEncoder();
    const entries = [{ name: 'private/instructions.yaml', bytes: encoder.encode(source) }];
    for (const file of [cvFile, transcriptFile].filter(Boolean)) {
      entries.push({ name: `private/${file.name}`, bytes: new Uint8Array(await file.arrayBuffer()) });
    }
    const files = [];
    const directory = [];
    let offset = 0;
    let directorySize = 0;
    for (const entry of entries) {
      const name = encoder.encode(entry.name);
      const crc = crc32(entry.bytes);
      const header = new Uint8Array(30);
      const local = new DataView(header.buffer);
      local.setUint32(0, 0x04034b50, true);
      local.setUint16(4, 20, true);
      local.setUint16(6, 0x0800, true); // UTF-8 filenames, stored without compression.
      local.setUint16(12, 33, true); // 1980-01-01, the earliest ZIP date.
      local.setUint32(14, crc, true);
      local.setUint32(18, entry.bytes.length, true);
      local.setUint32(22, entry.bytes.length, true);
      local.setUint16(26, name.length, true);
      files.push(header, name, entry.bytes);

      const record = new Uint8Array(46);
      const central = new DataView(record.buffer);
      central.setUint32(0, 0x02014b50, true);
      central.setUint16(4, 20, true);
      central.setUint16(6, 20, true);
      central.setUint16(8, 0x0800, true);
      central.setUint16(14, 33, true);
      central.setUint32(16, crc, true);
      central.setUint32(20, entry.bytes.length, true);
      central.setUint32(24, entry.bytes.length, true);
      central.setUint16(28, name.length, true);
      central.setUint32(42, offset, true);
      directory.push(record, name);
      directorySize += record.length + name.length;
      offset += header.length + name.length + entry.bytes.length;
    }
    const end = new Uint8Array(22);
    const footer = new DataView(end.buffer);
    footer.setUint32(0, 0x06054b50, true);
    footer.setUint16(8, entries.length, true);
    footer.setUint16(10, entries.length, true);
    footer.setUint32(12, directorySize, true);
    footer.setUint32(16, offset, true);
    return new Blob([...files, ...directory, end], { type: 'application/zip' });
  };
})();
