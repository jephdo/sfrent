import os
from flask_script import Manager

from sfrent import create_app

app = create_app(os.getenv('RENTTRACK_CONFIG', 'development'))

manager = Manager(app)


if __name__ == '__main__':
    manager.run()