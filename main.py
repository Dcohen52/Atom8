import json
import sys
import os
import logging
import time
from PyQt5.QtCore import Qt, QSize, QRect
from PyQt5.QtGui import QColor, QTextFormat, QPainter
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLineEdit, QLabel, QComboBox, \
    QListWidget, QHBoxLayout, QAction, QMessageBox, QFileDialog, QStatusBar, QCheckBox, QTextEdit, QInputDialog, \
    QDialog, QTableWidgetItem, QTableWidget, QMenu, QHeaderView, QPlainTextEdit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from helper import extract_elements_to_json


class QTextEditLogger(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.append(msg)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


class ScriptEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaWidth(self):
        digits = 1
        max_count = max(1, self.blockCount())
        while max_count >= 10:
            max_count /= 10
            digits += 1
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.lightGray)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, top, self.lineNumberArea.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlightCurrentLine(self):
        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)


class WebAutomationTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.driver = None
        self.steps = []
        self.recentFiles = []
        self.recentFilesMenu = None
        self.initUI()
        self.setupLogging()
        self.loadRecentFiles()
        self.currentFilePath = None
        self.resultsTable = None
        self.setupScriptEditor()

    def initUI(self):

        style = """
        QWidget {
            background-color: #FFFFFF;
            font-size: 12px;
        }

        QPushButton {
            color: white;
            background-color: #007BFF;
            border-radius: 4px;
            padding: 6px 12px;
            border: none;
            font-size: 12px;
        }

        QPushButton:hover {
            background-color: #0069D9;
            border-color: #0062CC;
        }

        QPushButton:pressed {
            background-color: #005CBF;
            border-color: #0056B3;
        }

        QLabel {
            color: #555;
        }

        QLineEdit {
            color: #555;
            border: 1px solid #ddd;
            padding: 6px;
            border-radius: 4px;
            background-color: #eee;
        }

        QLineEdit:focus {
            border-color: #007BFF;
            outline: none;
        }

        QStatusBar {
            background-color: #F7F7F7;
            color: #555;
        }

        QComboBox {
            border: 1px solid #ddd;
            padding: 10px;
            border-radius: 4px;
            background-color: #fff;
            color: #555;
        }

        QComboBox::drop-down {
            background-color: transparent;
        }

        QComboBox::down-arrow {
            image: url(/path/to/your/down-arrow-icon.png);
        }

        QComboBox QAbstractItemView {
            background-color: #fff;
            color: #555;
        }

        QListWidget {
            border: 1px solid #ddd;
            border-radius: 4px;
            color: #555;
            background-color: #f5f5f5;
        }

        QListWidget::item {
            padding: 4px;
            color: #555;
        }

        QListWidget::item:selected {
            background-color: #007BFF;
            color: white;
        }

        QTextEdit {
            border: 1px solid #ddd;
            color: #333;
            background-color: #f5f5f5;
        }

        QCheckBox {
            color: #555;
        }

        QMenuBar {
            color: #333;
        }

        QMenuBar::item {
            background-color: transparent;
        }

        QMenuBar::item:selected { 
            background-color: #D6D6D6;
        }

        QMenuBar::item:pressed {
            background-color: #C6C6C6;
        }

        QMenu {
            background-color: #FFFFFF;
            border: 1px solid #ddd;
        }

        QMenu::item {
            padding: 6px;
            width: 150px;
        }

        QMenu::item:selected {
            background-color: #007BFF;
            color: white;
        }

        QMenu::item:pressed {
            background-color: #0069D9;
            color: white;
        }
        """

        self.setWindowTitle('Atom8')
        self.setGeometry(100, 100, 800, 600)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        mainLayout = QVBoxLayout()
        self.setupMenuBar()
        self.setupActionSelection(mainLayout)
        self.setupButtonsAndStepsList(mainLayout)

        self.headlessCheckbox = QCheckBox("Headless Mode", self)
        self.headlessCheckbox.setChecked(False)
        mainLayout.addWidget(self.headlessCheckbox)
        self.headlessCheckbox.setToolTip("Run the browser in the background without GUI")

        self.logViewer = QTextEdit(self)
        self.logViewer.setReadOnly(True)
        mainLayout.addWidget(self.logViewer)

        buttonsLayout = QHBoxLayout()
        self.saveLogsButton = QPushButton('Save Logs', self)
        self.saveLogsButton.clicked.connect(self.saveLogs)
        buttonsLayout.addWidget(self.saveLogsButton)

        self.clearLogsButton = QPushButton('Clear Logs', self)
        self.clearLogsButton.clicked.connect(self.clearLogs)
        buttonsLayout.addWidget(self.clearLogsButton)

        mainLayout.addLayout(buttonsLayout)
        self.setStyleSheet(style)

        centralWidget = QWidget()
        centralWidget.setLayout(mainLayout)
        self.setCentralWidget(centralWidget)

    def setupMenuBar(self):
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu('File')
        toolsMenu = menuBar.addMenu('Tools')
        helpMenu = menuBar.addMenu('Help')

        newAction = QAction('New', self)
        newAction.triggered.connect(self.newFile)
        newAction.setShortcut('Ctrl+N')
        fileMenu.addAction(newAction)

        openAction = QAction('Open', self)
        openAction.triggered.connect(self.openFile)
        openAction.setShortcut('Ctrl+O')
        fileMenu.addAction(openAction)

        self.recentFilesMenu = fileMenu.addMenu('Open Recent')
        self.updateRecentFilesMenu()

        realSaveAction = QAction('Save', self)
        realSaveAction.triggered.connect(self.realSaveFile)
        realSaveAction.setShortcut('Ctrl+S')
        fileMenu.addAction(realSaveAction)

        saveAction = QAction('Save As', self)
        saveAction.triggered.connect(self.saveFile)
        saveAction.setShortcut('Ctrl+Shift+S')
        fileMenu.addAction(saveAction)

        clearAction = QAction('Clear All', self)
        clearAction.triggered.connect(self.clearStepsList)
        clearAction.setShortcut('Ctrl+N')
        fileMenu.addAction(clearAction)

        fileMenu.addSeparator()

        preferencesAction = QAction('Preferences', self)
        preferencesAction.triggered.connect(self.prefs)
        fileMenu.addAction(preferencesAction)
        preferencesAction.setShortcut('Ctrl+P')

        exitAction = QAction('Exit', self)
        exitAction.triggered.connect(self.close)
        exitAction.setShortcut('Ctrl+Q')
        fileMenu.addAction(exitAction)

        extractElementsAction = QAction('Extract Web Elements', self)
        extractElementsAction.triggered.connect(self.extractWebElements)
        extractElementsAction.setShortcut('Ctrl+E')
        toolsMenu.addAction(extractElementsAction)

        scriptEditorAction = QAction('Script Editor', self)
        scriptEditorAction.triggered.connect(self.showScriptEditor)
        toolsMenu.addAction(scriptEditorAction)

        aboutAction = QAction('About', self)
        aboutAction.triggered.connect(self.showAboutDialog)
        helpMenu.addAction(aboutAction)

    def addStep(self):
        action = self.actionSelection.currentText()
        locator_type = self.locatorSelection.currentText()
        locator_value = self.locatorInput.text()
        text_value = self.inputText.text()
        description_value = self.inputDescription.text()
        sleep_value = self.sleepInput.text()

        if action == 'Sleep':
            step = (action, sleep_value)
            display_txt = f'Sleep for {sleep_value} seconds.'
            self.logger.info(f"Added step: {display_txt}")
        elif action in ['Click Element', 'Input Text']:
            step = (action, locator_type, locator_value, text_value, description_value)
            display_txt = f'{action}: (By: {locator_type if locator_type != "Select Locator" else "N/A"}, {locator_value}){", Text: " + text_value if text_value else ""}, Description: {description_value}'
            self.logger.info(f"Added step: {display_txt}")
        elif action in ['Navigate to URL', 'Execute JavaScript', 'Execute Python Script']:
            step = (action, text_value, description_value)
            display_txt = f'{action}: {text_value}{"." if not description_value else f", Description: {description_value}"}'
            self.logger.info(f"Added step: {display_txt}")
        elif action == 'Maximize Window':
            step = (action,)
            display_txt = f'Maximize Window.'
            self.logger.info(f"Added step: {display_txt}")
        elif action == 'Take Screenshot':
            screenshot_filename = self.inputText.text()
            if not screenshot_filename.endswith('.png'):
                screenshot_filename += '.png'
            step = (action, screenshot_filename)
            display_txt = f'Take screenshot and save as {screenshot_filename}'
            self.logger.info(f"Added step: {display_txt}")
        else:
            QMessageBox.warning(self, "Invalid Action", "The selected action is not supported.")
            return

        self.steps.append(step)
        self.stepsList.addItem(display_txt)

    def setupActionSelection(self, layout):
        self.actionSelection = QComboBox(self)
        actions = ['Select Action', 'Navigate to URL', 'Click Element', 'Input Text', 'Take Screenshot',
                   'Execute JavaScript', 'Sleep', 'Execute Python Script', 'Maximize Window']
        self.actionSelection.addItems(actions)
        self.actionSelection.currentIndexChanged.connect(self.updateFields)

        actionSelectionLayout = QVBoxLayout()
        actionSelectionLayout.addWidget(QLabel('Select Action:'))
        actionSelectionLayout.addWidget(self.actionSelection)

        self.locatorSelection = QComboBox(self)
        locator_types = ['Select Locator', 'XPath', 'CSS Selector', 'ID', 'Name', 'Class Name', 'Tag Name', 'Link Text',
                         'Partial Link Text']
        self.locatorSelection.addItems(locator_types)

        self.locatorInput = QLineEdit(self)
        self.locatorInput.setPlaceholderText("Enter locator value")

        locatorLayout = QHBoxLayout()
        locatorLayout.addWidget(self.locatorSelection)
        locatorLayout.addWidget(self.locatorInput)

        actionSelectionLayout.addLayout(locatorLayout)

        self.inputText = QLineEdit(self)
        self.inputText.setPlaceholderText("Enter Text")

        self.sleepInput = QLineEdit(self)
        self.sleepInput.setPlaceholderText("Enter Sleep Time (in seconds)")

        self.inputDescription = QLineEdit(self)
        self.inputDescription.setPlaceholderText("Enter Description")

        fieldsLayout = QVBoxLayout()
        fieldsLayout.addWidget(self.inputText)
        fieldsLayout.addWidget(self.sleepInput)
        fieldsLayout.addWidget(self.inputDescription)

        actionSelectionLayout.addLayout(fieldsLayout)
        layout.addLayout(actionSelectionLayout)

    def setupButtonsAndStepsList(self, layout):
        self.editMode = False
        self.editIndex = None
        self.addButton = QPushButton('Add Step', self)
        self.addButton.clicked.connect(self.addOrEditStep)

        self.removeButton = QPushButton('Remove Selected Step', self)
        self.removeButton.clicked.connect(self.removeSelectedStep)

        self.editButton = QPushButton('Edit Selected Step', self)
        self.editButton.clicked.connect(self.editSelectedStep)

        self.saveButton = QPushButton('Save Changes', self)
        self.saveButton.clicked.connect(self.saveEditedStep)

        self.saveButton.setEnabled(True)
        self.saveButton.setVisible(False)

        self.stepsList = QListWidget(self)

        self.startButton = QPushButton('Run', self)
        self.startButton.clicked.connect(self.startAutomation)

        self.moveUpButton = QPushButton('Up', self)
        self.moveDownButton = QPushButton('Down', self)
        self.moveUpButton.clicked.connect(self.moveStepUp)
        self.moveDownButton.clicked.connect(self.moveStepDown)

        self.locatorSelection.setVisible(False)
        self.locatorInput.setVisible(False)
        self.inputText.setVisible(False)
        self.sleepInput.setVisible(False)
        self.inputDescription.setVisible(False)

        buttonsLayout = QHBoxLayout()
        buttonsLayout.addWidget(self.addButton)
        buttonsLayout.addWidget(self.editButton)
        buttonsLayout.addWidget(self.saveButton)
        buttonsLayout.addWidget(self.removeButton)
        buttonsLayout.addWidget(self.moveUpButton)
        buttonsLayout.addWidget(self.moveDownButton)
        buttonsLayout.addWidget(self.startButton)

        self.startButton.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: #28A745;
                border-radius: 4px;
                padding: 6px 12px;
                border: none;
                font-size: 12px;
            }

            QPushButton:hover {
                background-color: #218838;
                border-color: #1E7E34;
            }

            QPushButton:pressed {
                background-color: #1D7D33;
                border-color: #1C7430;
            }
        """)

        layout.addLayout(buttonsLayout)
        layout.addWidget(self.stepsList)

    def updateLocatorFields(self):
        locator_type = self.locatorSelection.currentText()
        self.locatorInput.setVisible(locator_type != 'Select Locator')

    def removeSelectedStep(self):
        selected_item = self.stepsList.currentRow()
        if selected_item >= 0:
            del self.steps[selected_item]
            self.stepsList.takeItem(selected_item)
            self.logger.info(f"Removed step at index {selected_item}.")
        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to remove.")

    def updateFields(self):
        action = self.actionSelection.currentText()

        if action in ['Click Element', 'Input Text']:
            self.locatorSelection.setVisible(True)
            self.locatorInput.setVisible(True)
        else:
            self.locatorSelection.setVisible(False)
            self.locatorInput.setVisible(False)

        self.inputText.setVisible(
            action in ['Input Text', 'Execute Python Script', 'Execute JavaScript', 'Navigate to URL',
                       'Take Screenshot'])
        self.sleepInput.setVisible(action == 'Sleep')
        self.inputDescription.setVisible(
            action in ['Click Element', 'Input Text', 'Sleep', 'Navigate to URL', 'Execute Python Script',
                       'Execute JavaScript'])

        if action == 'Navigate to URL':
            self.inputText.setPlaceholderText("Enter URL")
        elif action == 'Input Text':
            self.inputText.setPlaceholderText("Enter Text")
        elif action == 'Execute Python Script':
            self.inputText.setPlaceholderText("Enter Script Path")
        elif action == 'Execute JavaScript':
            self.inputText.setPlaceholderText("Enter JavaScript Code")
        elif action == 'Sleep':
            self.inputText.setPlaceholderText("Enter Sleep Time (in seconds)")
        elif action == 'Take Screenshot':
            self.inputText.setPlaceholderText("Enter Screenshot Name")
        else:
            self.inputText.setPlaceholderText("Enter Text")

    def startAutomation(self):
        chrome_options = Options()
        if self.headlessCheckbox.isChecked():
            chrome_options.add_argument("--headless")

        self.driver = webdriver.Chrome(options=chrome_options)

        locator_strategies = {
            'XPath': By.XPATH,
            'CSS Selector': By.CSS_SELECTOR,
            'ID': By.ID,
            'Name': By.NAME,
            'Class Name': By.CLASS_NAME,
            'Tag Name': By.TAG_NAME,
            'Link Text': By.LINK_TEXT,
            'Partial Link Text': By.PARTIAL_LINK_TEXT
        }

        for step in self.steps:
            action = step[0]

            try:
                if action == 'Navigate to URL':
                    self.driver.get(step[1])
                elif action in ['Click Element', 'Input Text']:
                    locator_type = step[1]
                    locator_value = step[2]
                    element = self.driver.find_element(locator_strategies[locator_type], locator_value)
                    if action == 'Click Element':
                        element.click()
                    else:
                        element.send_keys(step[3])
                elif action == 'Take Screenshot':
                    screenshot_name = f"{step[1]}{'.png' if not step[1].endswith('.png') else ''}"
                    self.driver.save_screenshot(screenshot_name)
                elif action == 'Execute JavaScript':
                    self.driver.execute_script(step[1])
                elif action == 'Sleep':
                    time.sleep(float(step[1]))
                elif action == 'Maximize Window':
                    self.driver.maximize_window()

            except Exception as e:
                self.logger.error(f"Error in {action}: {e}")

        self.driver.quit()
        self.logger.info("\n\nOperation completed successfully.\n\n")

    def setupLogging(self):
        self.logger = logging.getLogger('WebAutomationTool')
        logging.basicConfig(level=logging.INFO)

        logTextBox = QTextEditLogger(self.logViewer)
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(logTextBox)
        logging.getLogger().setLevel(logging.DEBUG)

    def showAboutDialog(self):
        QMessageBox.about(self, "About Atom8", """
        <html>
        <head>
            <style> 
                p { font-family: Arial, sans-serif; line-height: 1.6; }
                a { text-decoration: none; color: #007BFF; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <h2>Atom8 - Advanced Web Automation Tool</h2>
            <p><strong>Version:</strong> 0.1</p>
            <p>Atom8 is an advanced web automation tool designed for efficiency and ease of use. Ideal for both professionals and hobbyists, it simplifies complex web tasks through its advanced technology, offering a seamless automation experience. Atom8 excels in a wide range of applications from data scraping to intricate testing workflows.</p>
            <p>Atom8 is built on top of Selenium, a popular web automation framework. It is designed to be a user-friendly alternative to Selenium, offering a simple and intuitive interface for creating and running, simple and complex automation tasks.</p>
            <p><strong>Created by:</strong> Dekel Cohen</p>
            <p><strong>License:</strong> MIT License</p>

            <p>Discover more about Atom8, get updates, and access support on our GitHub page: <a href="https://github.com/Dcohen52/Atom8" target="_blank">Atom8 GitHub Repository</a>.</p>

            <p><strong>Disclaimer:</strong> Atom8 is an independent project, not officially affiliated with or endorsed by the Selenium project or its associates.</p>
        </body>
        </html>
        """)

    def saveFile(self):
        fileName, _ = QFileDialog.getSaveFileName(self, "Save As", "", "Atom8 Files (*.atm8)")
        if fileName:
            self.currentFilePath = fileName
            self.updateRecentFiles(fileName)
            with open(fileName, "w+") as file:
                json.dump(self.steps, file)
            self.statusBar.showMessage(f"File saved as {fileName} successfully.", 5000)

    def realSaveFile(self):
        if self.currentFilePath:
            with open(self.currentFilePath, "w") as file:
                json.dump(self.steps, file)
            self.statusBar.showMessage(f"File {self.currentFilePath} saved successfully.", 5000)
        else:
            self.saveFile()

    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Atom8 Files (*.atm8)")
        if fileName:
            self.currentFilePath = fileName
            self.updateRecentFiles(fileName)
            try:
                with open(fileName, "r") as file:
                    loaded_steps = json.load(file)
                    if not isinstance(loaded_steps, list):
                        raise ValueError("File content is not in the expected list format")

                    self.steps = loaded_steps
                    self.stepsList.clear()
                    for index, step in enumerate(self.steps):
                        if not isinstance(step, (list, tuple)):
                            QMessageBox.critical(self, "Error", f"Invalid step format at index {index}: {step}")
                            continue
                        display_text = self.constructStepDisplayText(step)
                        self.stepsList.addItem(display_text)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {e}")

    def constructStepDisplayText(self, step):
        try:
            action = step[0]
            if action == 'Sleep':
                display_text = f'Sleep for {step[1]} seconds.'
            elif action in ['Click Element', 'Input Text']:
                display_text = f'{action}: (By: {step[1]}, {step[2]}){", Text: " + step[3] if step[3] else ""}, Description: {step[4]}'
            elif action in ['Navigate to URL', 'Execute JavaScript', 'Execute Python Script']:
                display_text = f'{action}: {step[1]}{"." if not step[2] else f", Description: {step[2]}"}'
            elif action == 'Take Screenshot':
                display_text = f'Take screenshot and save as {step[1]}'
            else:
                display_text = f'{action}'
        except Exception as e:
            display_text = f'Error: {e}'
        return display_text

    def clearStepsList(self):
        self.stepsList.clear()
        self.steps.clear()
        self.clearInputFields()

    def prefs(self):
        self.prefsWindow = QDialog(self, Qt.Window)
        self.prefsWindow.setWindowTitle("Preferences")
        prefsLayout = QVBoxLayout()

        browserLabel = QLabel("Default Browser:")
        self.browserComboBox = QComboBox()
        self.browserComboBox.addItems(["Chrome", "Firefox", "Safari", "Edge"])
        self.browserComboBox.setCurrentText(self.loadSetting("defaultBrowser", "Chrome"))

        browserLayout = QHBoxLayout()
        browserLayout.addWidget(browserLabel)
        browserLayout.addWidget(self.browserComboBox)
        prefsLayout.addLayout(browserLayout)

        savePathLabel = QLabel("Default Save Path:")
        self.savePathLineEdit = QLineEdit()
        self.savePathLineEdit.setText(self.loadSetting("savePath", ""))
        savePathLayout = QHBoxLayout()
        savePathLayout.addWidget(savePathLabel)
        savePathLayout.addWidget(self.savePathLineEdit)
        prefsLayout.addLayout(savePathLayout)

        saveButton = QPushButton("Save")
        saveButton.clicked.connect(self.savePrefs)
        prefsLayout.addWidget(saveButton)

        self.prefsWindow.setLayout(prefsLayout)
        self.prefsWindow.resize(400, 200)
        self.prefsWindow.show()

    def savePrefs(self):
        self.saveSetting("defaultBrowser", self.browserComboBox.currentText())
        self.saveSetting("savePath", self.savePathLineEdit.text())
        self.prefsWindow.close()

    def saveSetting(self, key, value):
        settings = self.loadSettings()

        settings[key] = value

        with open('settings.json', 'w') as file:
            json.dump(settings, file)

    def loadSetting(self, key, defaultValue=None):
        settings = self.loadSettings()

        return settings.get(key, defaultValue)

    def loadSettings(self):
        try:
            with open('settings.json', 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.logger.warning("Failed to load settings file.")
            return {}

    def setupScriptEditor(self):
        self.scriptEditorWindow = QMainWindow(self)
        self.scriptEditorWindow.setWindowTitle("AQL Script Editor")
        self.scriptEditorWindow.setGeometry(100, 100, 600, 400)

        self.scriptEditor = QTextEdit(self.scriptEditorWindow)
        self.scriptEditor.setPlaceholderText("Enter AQL script here...")
        self.scriptEditor.setReadOnly(False)
        self.scriptEditorWindow.setCentralWidget(self.scriptEditor)

        self.scriptEditorStatusBar = QStatusBar()
        self.scriptEditorWindow.setStatusBar(self.scriptEditorStatusBar)

        self.scriptEditorMenuBar = self.scriptEditorWindow.menuBar()
        self.scriptEditorFileMenu = self.scriptEditorMenuBar.addMenu('File')

        self.scriptEditorOpenAction = QAction('Open', self)
        self.scriptEditorOpenAction.triggered.connect(self.openScriptFile)

        self.scriptEditorSaveAction = QAction('Save', self)
        self.scriptEditorSaveAction.triggered.connect(self.saveScriptFile)

        self.scriptEditorSaveAsAction = QAction('Save As', self)
        self.scriptEditorSaveAsAction.triggered.connect(self.saveScriptFileAs)

        self.scriptEditorClearAction = QAction('Clear', self)
        self.scriptEditorClearAction.triggered.connect(self.clearScriptEditor)

        self.scriptEditorCloseAction = QAction('Close', self)
        self.scriptEditorCloseAction.triggered.connect(self.closeScriptEditor)

        self.scriptEditorFileMenu.addAction(self.scriptEditorOpenAction)
        self.scriptEditorFileMenu.addAction(self.scriptEditorSaveAction)
        self.scriptEditorFileMenu.addAction(self.scriptEditorSaveAsAction)
        self.scriptEditorFileMenu.addAction(self.scriptEditorClearAction)
        self.scriptEditorFileMenu.addAction(self.scriptEditorCloseAction)

        self.scriptEditorStatusBar.showMessage("Ready", 5000)

        self.scriptEditorLogger = logging.getLogger('ScriptEditor')
        self.scriptEditorLogger.setLevel(logging.INFO)

        self.scriptEditorLoggerTextBox = QTextEditLogger(self.scriptEditor)
        self.scriptEditorLoggerTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.scriptEditorLogger.addHandler(self.scriptEditorLoggerTextBox)
        self.scriptEditorLogger.setLevel(logging.DEBUG)

    def openScriptFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*);;AQL Files (*.aql)")
        if fileName:
            try:
                with open(fileName, "r") as file:
                    self.scriptEditor.setText(file.read())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {e}")

    def saveScriptFile(self):
        if self.currentFilePath:
            with open(self.currentFilePath, "w") as file:
                file.write(self.scriptEditor.toPlainText())
            self.scriptEditorStatusBar.showMessage("File saved successfully.", 5000)
        else:
            self.saveScriptFileAs()

    def saveScriptFileAs(self):
        fileName, _ = QFileDialog.getSaveFileName(self, "Save As", "", "AQL Files (*.aql)")
        if fileName:
            self.currentFilePath = fileName
            with open(fileName, "w+") as file:
                file.write(self.scriptEditor.toPlainText())
            self.scriptEditorStatusBar.showMessage("File saved as new file.", 5000)

    def clearScriptEditor(self):
        self.scriptEditor.clear()

    def closeScriptEditor(self):
        self.scriptEditorWindow.close()

    def showScriptEditor(self):
        self.scriptEditorWindow.show()

    def newFile(self):
        if self.steps:
            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Question)
            msgBox.setText("Do you want to save the current file?")
            msgBox.setWindowTitle("Save File")
            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            msgBox.setDefaultButton(QMessageBox.Yes)
            response = msgBox.exec()

            if response == QMessageBox.Yes:
                self.realSaveFile()
                self.clearStepsList()
                self.clearInputFields()
            elif response == QMessageBox.No:
                self.clearStepsList()
                self.clearInputFields()
            elif response == QMessageBox.Cancel:
                return

    def saveLogs(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Logs", "", "Log Files (*.log)", options=options)
        if fileName:
            with open(fileName, "w") as file:
                file.write(self.logViewer.toPlainText())

    def clearLogs(self):
        self.logViewer.clear()

    def editSelectedStep(self):
        selected_item = self.stepsList.currentRow()
        if selected_item >= 0:
            self.editMode = True
            self.editIndex = selected_item
            self.editButton.setVisible(False)
            self.saveButton.setVisible(True)

            step = self.steps[selected_item]
            action = step[0]
            self.actionSelection.setCurrentText(action)
            if action in ['Click Element', 'Input Text']:
                self.locatorSelection.setVisible(True)
                self.locatorInput.setVisible(True)
                self.locatorSelection.setCurrentText(step[1])
                self.locatorInput.setText(step[2])
            else:
                self.locatorSelection.setVisible(False)
                self.locatorInput.setVisible(False)

            self.inputText.setVisible(
                action in ['Input Text', 'Execute Python Script', 'Execute JavaScript', 'Navigate to URL',
                           'Take Screenshot'])
            self.sleepInput.setVisible(action == 'Sleep')
            self.inputDescription.setVisible(
                action in ['Click Element', 'Input Text', 'Sleep', 'Navigate to URL', 'Execute Python Script',
                           'Execute JavaScript'])

            if action == 'Navigate to URL':
                self.inputText.setPlaceholderText("Enter URL")
                self.inputText.setText(step[1])
            elif action == 'Input Text':
                self.inputText.setPlaceholderText("Enter Text")
                self.inputText.setText(step[3])
            elif action == 'Execute Python Script':
                self.inputText.setPlaceholderText("Enter Script Path")
                self.inputText.setText(step[1])
            elif action == 'Execute JavaScript':
                self.inputText.setPlaceholderText("Enter JavaScript Code")
                self.inputText.setText(step[1])
            elif action == 'Sleep':
                self.inputText.setPlaceholderText("Enter Sleep Time (in seconds)")
                self.inputText.setText(step[1])
            elif action == 'Take Screenshot':
                self.inputText.setPlaceholderText("Enter Screenshot Name")
                self.inputText.setText(step[1])
            else:
                self.inputText.setPlaceholderText("Enter Text")
                self.inputText.setText(step[1])

            self.inputDescription.setText(step[-1])
        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to edit.")

    def updateStep(self):
        selected_item = self.stepsList.currentRow()
        if selected_item >= 0:
            action = self.actionSelection.currentText()
            locator_type = self.locatorSelection.currentText()
            locator_value = self.locatorInput.text()
            text_value = self.inputText.text()
            sleep_value = self.sleepInput.text()
            description_value = self.inputDescription.text()

            if action == 'Sleep':
                step = (action, sleep_value)
                display_txt = f'Sleep for {sleep_value} seconds.'
            elif action in ['Click Element', 'Input Text']:
                step = (action, locator_type, locator_value, text_value, description_value)
                display_txt = f'{action}: {locator_value if locator_value else text_value} (Locator: {locator_type if locator_type != "Select Locator" else "N/A"}), Description: {description_value}'
            elif action in ['Navigate to URL', 'Execute JavaScript', 'Execute Python Script']:
                step = (action, text_value, description_value)
                display_txt = f'{action}: {text_value}{"." if not description_value else f", Description: {description_value}"}'
            elif action == 'Take Screenshot':
                step = (action, text_value, description_value)
                display_txt = f'Take screenshot and save as {text_value}{".png" if not text_value.endswith(".png") else ""}{"." if not description_value else f", Description: {description_value}"}'
            elif action == 'Maximize Window':
                step = action
                display_txt = f'Maximize Window.'
            else:
                QMessageBox.warning(self, "Invalid Action", "The selected action is not supported.")
                return

            self.steps[selected_item] = step
            self.stepsList.item(selected_item).setText(display_txt)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to update.")

    def moveStepUp(self):
        selected_item = self.stepsList.currentRow()
        if selected_item >= 1:
            self.stepsList.insertItem(selected_item - 1, self.stepsList.takeItem(selected_item))
            self.steps.insert(selected_item - 1, self.steps.pop(selected_item))
            self.stepsList.setCurrentRow(selected_item - 1)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to move up.")

    def moveStepDown(self):
        selected_item = self.stepsList.currentRow()
        if selected_item >= 0 and selected_item < self.stepsList.count() - 1:
            self.stepsList.insertItem(selected_item + 1, self.stepsList.takeItem(selected_item))
            self.steps.insert(selected_item + 1, self.steps.pop(selected_item))
            self.stepsList.setCurrentRow(selected_item + 1)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to move down.")

    def addOrEditStep(self):
        if self.editMode:
            self.updateStep()
            self.editMode = False
            self.editIndex = None
            self.editButton.setVisible(True)
            self.saveButton.setVisible(False)
        else:
            self.addStep()

    def saveEditedStep(self):
        self.updateStep()
        self.editMode = False
        self.editIndex = None
        self.editButton.setVisible(True)
        self.saveButton.setVisible(False)
        self.clearInputFields()

        self.logger.info("Saved edited step.")

    def clearInputFields(self):
        self.actionSelection.setCurrentIndex(0)
        self.locatorSelection.setCurrentIndex(0)
        self.locatorInput.setText('')
        self.inputText.setText('')
        self.sleepInput.setText('')
        self.inputDescription.setText('')

    def updateRecentFiles(self, filePath):
        if filePath not in self.recentFiles:
            self.recentFiles.append(filePath)
            self.updateRecentFilesMenu()

    def updateRecentFilesMenu(self):
        self.recentFilesMenu.clear()
        for filePath in self.recentFiles:
            action = QAction(filePath, self)
            action.triggered.connect(lambda checked, path=filePath: self.openRecentFile(path))
            self.recentFilesMenu.addAction(action)

    def openRecentFile(self, filePath):
        try:
            with open(filePath, "r") as file:
                self.steps = json.load(file)
                self.stepsList.clear()
                for step in self.steps:
                    display_text = self.constructStepDisplayText(step)
                    self.stepsList.addItem(display_text)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file: {e}")

    def loadRecentFiles(self):
        if os.path.exists('recent_files.json'):
            with open('recent_files.json', 'r') as file:
                self.recentFiles = json.load(file)
                self.updateRecentFilesMenu()

        self.logger.info("Loaded recent files.")

    def closeEvent(self, event):
        self.saveRecentFiles()
        super().closeEvent(event)

    def saveRecentFiles(self):
        with open('recent_files.json', 'w') as file:
            json.dump(self.recentFiles, file)

    def extractWebElements(self):
        url, ok = QInputDialog.getText(self, 'Extract Web Elements', 'Enter the URL:')
        if ok and url:
            try:
                elements_data = extract_elements_to_json(url)
                self.showExtractionResult(elements_data)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to extract elements: {e}")

    def showExtractionResult(self, elements_data):
        self.resultsWindow = QDialog(self, Qt.Window)
        self.resultsWindow.setWindowTitle("Extraction Results")
        resultsLayout = QVBoxLayout()

        self.urlInputField = QLineEdit(self.resultsWindow)
        self.urlInputField.setPlaceholderText('Enter URL')
        resultsLayout.addWidget(self.urlInputField)

        searchButton = QPushButton('Extract Web Elements', self.resultsWindow)
        searchButton.clicked.connect(self.onSearchClicked)
        resultsLayout.addWidget(searchButton)

        self.resultsTable = QTableWidget()
        self.updateResultsTable(elements_data)
        resultsLayout.addWidget(self.resultsTable)

        self.resultsWindow.setLayout(resultsLayout)
        self.resultsWindow.resize(600, 400)
        self.resultsWindow.show()

    def updateResultsTable(self, elements_data):
        self.resultsTable.setColumnCount(2)
        self.resultsTable.setHorizontalHeaderLabels(['Value', 'Locators'])
        self.resultsTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.resultsTable.verticalHeader().setVisible(False)
        self.resultsTable.setEditTriggers(QTableWidget.NoEditTriggers)

        self.resultsTable.setRowCount(len(elements_data))
        for row, element in enumerate(elements_data):
            self.resultsTable.setRowHeight(row, 45)
            self.resultsTable.setItem(row, 0, QTableWidgetItem(element['value']))
            comboBox = QComboBox()
            for locator in element['locators']:
                comboBox.addItem(f"XPath: {locator['xpath']}")
                for attr, value in locator['attributes'].items():
                    comboBox.addItem(f"{attr}: {value}")
            self.resultsTable.setCellWidget(row, 1, comboBox)

    def onSearchClicked(self):
        url = self.urlInputField.text()
        if url:
            self.statusBar.showMessage("Extracting all web elements...")
            QApplication.processEvents()

            try:
                elements_data = extract_elements_to_json(url)
                self.updateResultsTable(elements_data)
                self.statusBar.clearMessage()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to extract elements: {e}")
                self.statusBar.clearMessage()

    def contextMenuEvent(self, event, comboBox):
        menu = QMenu()
        copyAction = QAction("Copy", self)
        copyAction.triggered.connect(lambda: QApplication.clipboard().setText(comboBox.currentText().split(": ")[-1]))
        menu.addAction(copyAction)
        menu.exec_(event.globalPos())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = WebAutomationTool()
    ex.show()
    sys.exit(app.exec_())
