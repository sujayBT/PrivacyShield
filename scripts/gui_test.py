import sys
from PyQt5.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv)
label = QLabel("PyQt5 is working!")
label.setWindowTitle("GUI Test")
label.resize(300, 100)
label.show()

sys.exit(app.exec_())
