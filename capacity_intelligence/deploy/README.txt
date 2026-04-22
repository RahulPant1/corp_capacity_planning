Capacity Intelligence — Installation Guide
==========================================

PRE-REQUISITE
  Python 3.9 or later must be available in your terminal or command prompt.
  If your team policy requires a virtual environment, activate it before
  running install.bat. The scripts do not create or activate one for you.

INSTALL  (run once, or when upgrading to a new version)
  1. Open a Command Prompt in this folder.
  2. Run:  install.bat
     This installs the app and all its dependencies from the .whl file here.

RUN  (every time you want to use the app)
  Double-click run.bat  — or run:  capacity-intelligence
  The app opens automatically in your browser at http://localhost:8501

  On first launch go to  Admin -> Load Sample Data  to activate all tabs.

UPGRADE
  When a new .whl is shared, drop it in the same folder and re-run install.bat.
  The --upgrade flag updates to the latest version automatically.

UNINSTALL
  pip uninstall capacity-intelligence
