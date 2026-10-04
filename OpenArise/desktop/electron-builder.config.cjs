const path = require('node:path');
module.exports = {
  appId: 'ide.openarise.desktop',
  productName: 'OpenArise',
  executableName: 'OpenArise',
  artifactName: 'OpenArise-${version}-win-${arch}.${ext}',
  directories: { output: 'release' },
  asar: true,
  files: ['dist/**', 'dist-electron/**', 'build/icon.png', 'package.json', '!node_modules/**', '!**/*.map', '!dist/win-unpacked/**'],
  extraResources: [
    { from: '.packaging/windows-python', to: 'ai-engine/.venv/Scripts', filter: ['**/*', '!**/__pycache__/**', '!**/*.pyc'] },
    { from: '../ai-engine/app', to: 'ai-engine/app', filter: ['**/*', '!**/__pycache__/**', '!**/*.pyc'] },
    { from: '../ai-engine/requirements.txt', to: 'ai-engine/requirements.txt' },
    { from: 'python', to: 'desktop/python', filter: ['**/*', '!**/__pycache__/**', '!**/*.pyc'] },
  ],
  electronDist: path.resolve(__dirname, 'node_modules/electron/dist'),
  npmRebuild: false,
  win: { icon: 'build/icon.png', target: [{ target: 'nsis', arch: ['x64'] }] },
  portable: { artifactName: 'OpenArise-${version}-win-${arch}-portable.exe' },
  nsis: { artifactName: 'OpenArise-${version}-win-${arch}-setup.exe', oneClick: false, perMachine: false, allowToChangeInstallationDirectory: true, createDesktopShortcut: true, shortcutName: 'OpenArise' },
  msi: { artifactName: 'OpenArise-${version}-win-${arch}-setup.msi', oneClick: false, perMachine: false, createDesktopShortcut: true, createStartMenuShortcut: true, shortcutName: 'OpenArise', runAfterFinish: false },
};