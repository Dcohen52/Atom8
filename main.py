import json
import sys
import os
import logging
import time
from PyQt5.QtWidgets import QTextEdit

from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLineEdit, QLabel, QComboBox, \
    QListWidget, QHBoxLayout, QAction, QMessageBox, QFileDialog, QStatusBar, QCheckBox, QTextEdit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


class QTextEditLogger(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.append(msg)


class WebAutomationTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.driver = None
        self.steps = []
        self.initUI()
        self.setupLogging()

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
        """

        self.setWindowTitle('Atom8 - Advanced Web Automation Tool')
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
        helpMenu = menuBar.addMenu('Help')

        openAction = QAction('Open', self)
        openAction.triggered.connect(self.openFile)
        saveAction = QAction('Save', self)
        saveAction.triggered.connect(self.saveFile)
        fileMenu.addAction(openAction)

        fileMenu.addAction(saveAction)
        fileMenu.addSeparator()
        aboutAction = QAction('About', self)
        aboutAction.triggered.connect(self.showAboutDialog)
        helpMenu.addAction(aboutAction)

        clearAction = QAction('Clear', self)
        clearAction.triggered.connect(self.clearStepsList)
        fileMenu.addAction(clearAction)

        exitAction = QAction('Exit', self)
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)

    def addStep(self):
        action = self.actionSelection.currentText()
        input_value = self.inputField.text()
        text_value = self.inputText.text()
        description_value = self.inputDescription.text()
        sleep_value = self.sleepInput.text()

        if action == 'Sleep' and sleep_value:
            step = (action, sleep_value, '', description_value)
            self.steps.append(step)
            self.stepsList.addItem(f'{action}: Sleep for {sleep_value} seconds, Description: {description_value}')
        elif input_value:
            step = (action, input_value, text_value, description_value)
            self.steps.append(step)
            self.stepsList.addItem(f'{action}: {input_value}, Text: {text_value}, Description: {description_value}')
        else:
            QMessageBox.warning(self, "Invalid Input", "Please provide valid input for the selected action.")

        self.inputField.clear()
        self.inputText.clear()
        self.sleepInput.clear()
        self.inputDescription.clear()

    def setupActionSelection(self, layout):
        self.actionSelection = QComboBox(self)
        actions = ['Select Action', 'Navigate to URL', 'Click Element', 'Input Text', 'Take Screenshot',
                   'Execute JavaScript', 'Sleep']
        self.actionSelection.addItems(actions)

        actionSelectionLayout = QVBoxLayout()
        actionSelectionLayout.addWidget(QLabel('Select Action:'))
        actionSelectionLayout.addWidget(self.actionSelection)

        self.inputField = QLineEdit(self)
        self.inputField.setPlaceholderText("Enter URL or XPath")

        self.inputText = QLineEdit(self)
        self.inputText.setPlaceholderText("Enter Text")

        self.sleepInput = QLineEdit(self)
        self.sleepInput.setPlaceholderText("Enter Sleep Time (in seconds)")

        self.inputDescription = QLineEdit(self)
        self.inputDescription.setPlaceholderText("Enter Description")

        fieldsLayout = QVBoxLayout()
        fieldsLayout.addWidget(self.inputField)
        fieldsLayout.addWidget(self.inputText)
        fieldsLayout.addWidget(self.sleepInput)
        fieldsLayout.addWidget(self.inputDescription)

        actionSelectionLayout.addLayout(fieldsLayout)
        layout.addLayout(actionSelectionLayout)

        self.actionSelection.currentIndexChanged.connect(self.updateFields)

        self.updateFields()

    def setupButtonsAndStepsList(self, layout):
        self.editMode = False
        self.editIndex = None
        self.addButton = QPushButton('Add/Edit Step', self)
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

        self.startButton = QPushButton('Start Automation', self)
        self.startButton.clicked.connect(self.startAutomation)

        self.moveUpButton = QPushButton('Move Step Up', self)
        self.moveDownButton = QPushButton('Move Step Down', self)
        self.moveUpButton.clicked.connect(self.moveStepUp)
        self.moveDownButton.clicked.connect(self.moveStepDown)

        buttonsLayout = QHBoxLayout()
        buttonsLayout.addWidget(self.addButton)
        buttonsLayout.addWidget(self.editButton)
        buttonsLayout.addWidget(self.saveButton)
        buttonsLayout.addWidget(self.removeButton)
        buttonsLayout.addWidget(self.startButton)
        buttonsLayout.addWidget(self.moveUpButton)
        buttonsLayout.addWidget(self.moveDownButton)

        layout.addLayout(buttonsLayout)
        layout.addWidget(self.stepsList)

    def removeSelectedStep(self):
        selected_item = self.stepsList.currentRow()
        if selected_item >= 0:
            self.stepsList.takeItem(selected_item)
            del self.steps[self.stepsList.currentRow()]
        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to remove.")

    def updateFields(self):
        action = self.actionSelection.currentText()

        self.inputField.setVisible(False)
        self.inputText.setVisible(False)
        self.sleepInput.setVisible(False)
        self.inputDescription.setVisible(False)
        self.inputField.setPlaceholderText("")
        self.inputText.setPlaceholderText("")
        self.sleepInput.setPlaceholderText("")

        if action in ['Navigate to URL', 'Click Element', 'Input Text']:
            self.inputField.setVisible(True)
            self.inputDescription.setVisible(True)
            if action == 'Navigate to URL':
                self.inputField.setPlaceholderText("Enter URL")
                self.inputDescription.setVisible(True)
            elif action == 'Click Element':
                self.inputField.setPlaceholderText("Enter XPath")
                self.inputDescription.setVisible(True)
            elif action == 'Input Text':
                self.inputField.setPlaceholderText("Enter XPath")
                self.inputText.setVisible(True)
                self.inputText.setPlaceholderText("Enter Text")
                self.inputDescription.setVisible(True)

        if action == 'Sleep':
            self.sleepInput.setVisible(True)
            self.sleepInput.setPlaceholderText("Enter Sleep Time (in seconds)")
            self.inputDescription.setVisible(True)

        if action == 'Execute JavaScript':
            self.inputField.setVisible(True)
            self.inputField.setPlaceholderText("Enter JavaScript")
            self.inputDescription.setVisible(True)

        if action == 'Take Screenshot':
            self.inputField.setVisible(True)
            self.inputField.setPlaceholderText("Enter Screenshot Name")
            self.inputDescription.setVisible(True)

    def startAutomation(self):
        chrome_options = Options()
        if self.headlessCheckbox.isChecked():
            chrome_options.add_argument("--headless")

        self.driver = webdriver.Chrome(options=chrome_options)
        for action, value, text, description in self.steps:
            try:
                if action == 'Navigate to URL':
                    self.driver.get(value)
                elif action == 'Click Element':
                    element = self.driver.find_element(By.XPATH, value)
                    element.click()
                elif action == 'Input Text':
                    element = self.driver.find_element(By.XPATH, value)
                    element.send_keys(text)
                elif action == 'Take Screenshot':
                    timestamp = time.strftime("%Y%m%d%H%M%S")
                    screenshot_filename = f"{value}_{timestamp}.png"
                    self.driver.save_screenshot(screenshot_filename)
                elif action == 'Execute JavaScript':
                    self.driver.execute_script(value)
                elif action == 'Sleep':
                    sleep_time = float(value)
                    time.sleep(sleep_time)
            except Exception as e:
                self.logger.error(f"Error in {action}: {e}")
        self.driver.quit()

    def setupLogging(self):
        self.logger = logging.getLogger('WebAutomationTool')
        logging.basicConfig(level=logging.INFO)

        logTextBox = QTextEditLogger(self.logViewer)
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(logTextBox)
        logging.getLogger().setLevel(logging.DEBUG)

    def showAboutDialog(self):
        QMessageBox.about(self, "About Atom8", """
        <p>Atom8 - Advanced Web Automation Tool</p>
        <p>Version 0.1</p>
        <p>Atom8 is a tool for automating web tasks. It is built to be simple and easy to use.</p>
        <p>Created by Dekel Cohen</p>
        """)

    def saveFile(self):
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*);;Atom8 Files (*.atm8)")
        if fileName:
            with open(fileName, "w+") as file:
                json.dump(self.steps, file)

    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*);;Atom8 Files (*.atm8)")
        if fileName:
            with open(fileName, "r") as file:
                self.steps = json.load(file)
                self.stepsList.clear()
                for step in self.steps:

                    display_text = f'{step[0]}: {step[1]}, Text: {step[2]}, Description: {step[3]}'
                    if step[0] == 'Sleep':
                        display_text = f'{step[0]}: Sleep for {step[1]} seconds, Description: {step[3]}'
                    self.stepsList.addItem(display_text)

    def clearStepsList(self):
        self.stepsList.clear()
        self.steps = []

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
            step = self.steps[selected_item]
            action = step[0]
            input_value = step[1]
            text_value = step[2]
            description_value = step[3]
            sleep_value = step[1] if action == 'Sleep' else ''

            self.actionSelection.setCurrentText(action)
            self.inputField.setText(input_value)
            self.inputText.setText(text_value)
            self.inputDescription.setText(description_value)
            self.sleepInput.setText(sleep_value)
            self.saveButton.setVisible(True)
            self.editButton.setVisible(False)

        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to edit.")

    def updateStep(self):
        selected_item = self.stepsList.currentRow()
        if selected_item >= 0:
            action = self.actionSelection.currentText()
            input_value = self.inputField.text()
            text_value = self.inputText.text()
            description_value = self.inputDescription.text()
            sleep_value = self.sleepInput.text()

            if action == 'Sleep' and sleep_value:
                self.stepsList.item(selected_item).setText(
                    f'{action}: Sleep for {sleep_value} seconds, Description: {description_value}')
            elif input_value:
                self.stepsList.item(selected_item).setText(
                    f'{action}: {input_value}, Text: {text_value}, Description: {description_value}')
            else:
                QMessageBox.warning(self, "Invalid Input", "Please provide valid input for the selected action.")

            self.steps[selected_item] = (action, input_value, text_value, description_value)
            self.stepsList.item(selected_item).setText(
                f'{action}: {input_value}, Text: {text_value}, Description: {description_value}')
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
        if self.editMode and self.editIndex is not None:
            action = self.actionSelection.currentText()
            input_value = self.inputField.text()
            text_value = self.inputText.text()
            description_value = self.inputDescription.text()
            sleep_value = self.sleepInput.text() if action == 'Sleep' else ''

            updated_step = (action, input_value, text_value, description_value, sleep_value)
            self.steps[self.editIndex] = updated_step

            display_text = f'{action}: {input_value}, Text: {text_value}, Description: {description_value}'
            if action == 'Sleep':
                display_text = f'{action}: Sleep for {sleep_value} seconds, Description: {description_value}'
            self.stepsList.item(self.editIndex).setText(display_text)

            self.editMode = False
            self.editIndex = None
            self.editButton.setVisible(True)
            self.saveButton.setVisible(False)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a step to save.")

    def clearInputFields(self):
        self.actionSelection.setCurrentIndex(0)
        self.inputField.clear()
        self.inputText.clear()
        self.inputDescription.clear()
        self.sleepInput.clear()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = WebAutomationTool()
    ex.show()
    sys.exit(app.exec_())
