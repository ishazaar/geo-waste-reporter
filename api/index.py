import sys
import os

# Add root folder to sys.path so app and its modules import properly on Vercel
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Export app for Vercel Serverless Function
if __name__ == "__main__":
    app.run()
