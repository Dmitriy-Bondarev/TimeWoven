import random
import hashlib
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, Depends, UploadFile, File, Form

from fastapi.responses import HTMLResponse

@app.get("/family/tree", response_class=HTMLResponse)
def family_tree():
    return "<h1>OK FAMILY TREE</h1>"

