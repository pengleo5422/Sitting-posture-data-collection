import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, qApp


class MGen(QMainWindow):
    def __init__(self):
        super().__init__()


        exit_action = QAction('Exit', self)

        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(exit_action)

        self.show()

    def init_ui(self):
        pass

if __name__ == '__main__':

    app = QApplication(sys.argv)
    mgen = MGen()
    sys.exit(app.exec_())