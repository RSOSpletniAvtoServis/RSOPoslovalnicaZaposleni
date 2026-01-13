from typing import Union

from fastapi import FastAPI

import mysql.connector

app = FastAPI()


@app.get("/")
def read_root():
    return {"Mikrostoritev": "PoslovalnicaZaposleni"}

@app.get("/items/")
def read_items():
    return {"Tu": "So izdelki"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
    
