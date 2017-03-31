from datetime import datetime

def display(msg):
    print('['+datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + msg)

