const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let mainWindow;
let flaskProcess;
const PORT = 5000;

function getFlaskExePath() {
  // In dev mode, we skip launching the EXE
  if (require('electron-is-dev')) {
    return null;
  }
  // In production, the RhythmQuest.exe is in the same folder as this app
  const exePath = path.join(path.dirname(app.getPath('exe')), 'backend', 'run_server.exe');
  return exePath;
}

function waitForFlask(url, retries, callback) {
  const http = require('http');
  http.get(url, (res) => {
    callback(true);
  }).on('error', () => {
    if (retries > 0) {
      setTimeout(() => waitForFlask(url, retries - 1, callback), 500);
    } else {
      callback(false);
    }
  });
}

function startFlaskBackend() {
  const exePath = getFlaskExePath();
  if (!exePath || !fs.existsSync(exePath)) {
    console.log('Running in dev mode or EXE not found, skipping Flask launch.');
    return;
  }

  flaskProcess = spawn(exePath, [], {
    cwd: path.dirname(exePath),
    detached: false,
    windowsHide: true, // Hide the console window completely
    stdio: 'ignore'
  });

  flaskProcess.on('error', (err) => console.error('Flask process error:', err));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'RhythmQuest',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    // Make it look like a proper desktop app — no browser chrome
    autoHideMenuBar: true,
  });

  // Remove the menu bar entirely
  mainWindow.setMenuBarVisibility(false);

  mainWindow.loadURL(`http://127.0.0.1:${PORT}`);

  // Open external links in the default browser, not Electron
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

  // Wait for Flask to be ready before opening the window
  waitForFlask(`http://127.0.0.1:${PORT}`, 20, (ready) => {
    if (ready) {
      createWindow();
    } else {
      console.error('Flask failed to start');
      app.quit();
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // Kill Flask when window is closed
  if (flaskProcess) {
    flaskProcess.kill();
  }
  if (process.platform !== 'darwin') app.quit();
});
