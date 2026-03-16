const { app, BrowserWindow, shell, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const http = require('http');

let mainWindow;
let flaskProcess;
const PORT = 5000;

function getFlaskExePath() {
  const exePath = path.join(process.resourcesPath, 'backend', 'run_server.exe');
  if (fs.existsSync(exePath)) {
    return exePath;
  }
  // Show an explicit error for debugging the path
  dialog.showErrorBox('Backend Not Found', `Attempted to find backend at:\n${exePath}\n\nprocess.resourcesPath:\n${process.resourcesPath}`);
  return null;
}

function waitForFlask(retries, callback) {
  http.get(`http://127.0.0.1:${PORT}`, (res) => {
    callback(true);
  }).on('error', () => {
    if (retries > 0) {
      setTimeout(() => waitForFlask(retries - 1, callback), 500);
    } else {
      callback(false);
    }
  });
}

function startFlaskBackend() {
  const exePath = getFlaskExePath();

  if (!exePath) {
    console.log('Backend EXE not found - assuming dev mode (Flask should already be running).');
    return;
  }

  console.log('Starting Flask backend from:', exePath);

  flaskProcess = spawn(exePath, [], {
    cwd: path.dirname(exePath),
    detached: false,
    windowsHide: true,
    stdio: 'ignore'
  });

  flaskProcess.on('error', (err) => {
    console.error('Flask process error:', err);
    dialog.showErrorBox('Backend Error', 'Failed to start the application backend.\n\n' + err.message);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'RhythmQuest',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    autoHideMenuBar: true,
    show: false,  // Don't show until loaded
  });

  mainWindow.setMenuBarVisibility(false);

  mainWindow.loadURL(`http://127.0.0.1:${PORT}`);

  // Show window only when fully loaded
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('Page failed to load:', errorDescription);
    // Retry loading after a second
    setTimeout(() => {
      if (mainWindow) mainWindow.loadURL(`http://127.0.0.1:${PORT}`);
    }, 1000);
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startFlaskBackend();

  // Wait up to 30 seconds for Flask to be ready (60 x 500ms)
  waitForFlask(60, (ready) => {
    if (ready) {
      createWindow();
    } else {
      dialog.showErrorBox(
        'Startup Error',
        'Could not connect to the application backend after 30 seconds.\n\nPlease try launching the app again.'
      );
      app.quit();
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (flaskProcess) {
    flaskProcess.kill();
  }
  if (process.platform !== 'darwin') app.quit();
});
