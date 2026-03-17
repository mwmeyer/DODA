import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from tui import DodaTUI

if __name__ == "__main__":
    app = DodaTUI()
    app.run()
