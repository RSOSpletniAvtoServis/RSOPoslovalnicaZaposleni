from typing import Union

from fastapi import FastAPI

from fastapi import HTTPException
import mysql.connector
from mysql.connector import pooling
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import re
import httpx
import os
import requests

adminbaza = os.getenv("ADMINBAZA", "RSOAdminVozila")
SERVICE_ADMVOZ_URL = os.getenv("SERVICE_ADMVOZ_URL")

def validate_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
        raise ValueError("Invalid database name")
    return name

app = FastAPI()

try:
    pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        host="34.44.150.229",
        user="zan",
        password=">tnitm&+NqgoA=q6",
        database="RSOPoslovalnicaZaposleni",
        autocommit=True
    )
except Exception as e:
    print("Error: ",e)
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins (dev only!)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"Mikrostoritev": "PoslovalnicaZaposleni"}

# Zacetek Avtoservis

@app.get("/avtoservis/{idtennant}")
def get_avtoservis(idtennant: int):
    try:
        with pool.get_connection() as conn:
            with conn.cursor() as cursor:
                query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
                cursor.execute(query,(idtennant,))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="DB not found")
                tennantDB = row[1]
                
                sql = "SELECT IDAvtoServis, NazivAvtoServis, IDVodja FROM " + tennantDB + ".AvtoServis"
                cursor.execute(sql)

                row = cursor.fetchone()

                if row is None:
                    raise HTTPException(status_code=404, detail="Kraj not found")

                return {
                    "IDAvtoServis": row[0],
                    "NazivAvtoServis": row[1],
                    "IDVodja": row[2],
                }

    except HTTPException:
        raise
    except Exception as e:
        print("DB error:", e)
        raise HTTPException(status_code=500, detail="Database error")
    return {"Kraji": "undefined"}

# Konec avtoservis

# Zacetek poslovalnice

class Poslovalnica(BaseModel):
    naziv: str
    naslov: str
    telefon: str
    email: str
    idkraj: str
    idtennant: str
    uniqueid: str

class Posl(BaseModel):
    idtennant: str
    uniqueid: str
    
class Poslovalnica1(BaseModel):
    idposlovalnica: str
    naziv: str
    naslov: str
    telefon: str
    email: str
    idkraj: str
    aktiven: str
    idtennant: str
    uniqueid: str

@app.post("/dodajposlovalnico/")
def dodajPoslovalnico(poslovalnica: Poslovalnica):
    userid = poslovalnica.uniqueid
    try:
        conn = pool.get_connection()
        # Create a cursor
        cursor = conn.cursor()
        query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
        cursor.execute(query,(poslovalnica.idtennant,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="DB not found")
        tennantDB = row[1]
        
        query = "INSERT INTO " + tennantDB + ".Poslovalnica(NazivPoslovalnice,NaslovPoslovalnice,Telefon,Email,IDKraj,Aktiven) VALUES (%s,%s,%s,%s,%s,%s)"
        cursor.execute(query,(poslovalnica.naziv,poslovalnica.naslov,poslovalnica.telefon,poslovalnica.email,poslovalnica.idkraj,1))
        return {"Poslovalnica": "passed"}
  
    except Exception as e:
        print("Error: ", e)
        return {"Poslovalnica": "failed"}
    finally:
        cursor.close()
        conn.close() 
    return {"Poslovalnica": "unknown"}    
    
    
@app.post("/poslovalnice/")
def get_poslovalnice(posl: Posl):
    userid = posl.uniqueid
    try:
        with pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # get tennant db
                query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
                cursor.execute(query,(posl.idtennant,))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="DB not found")
                tennantDB = row[1]
                
                cursor.execute("SELECT IDKraj FROM "+ tennantDB +".Poslovalnica")
                rows = cursor.fetchall()
                kraji_ids = list({
                row[0]
                for row in rows
                if row[0] is not None
                })
                print(kraji_ids)
                fail = 0
                try:
                    data = {"ids": kraji_ids, "uniqueid": posl.uniqueid}
                    response = requests.post(f"{SERVICE_ADMVOZ_URL}/izbranikraji/", json=data, timeout=5)
                    #response.raise_for_status()  # Raise exception for HTTP errors  
                    print(response)
                    if "application/json" not in response.headers.get("Content-Type", ""):
                        sql = "SELECT IDPoslovalnica, NazivPoslovalnice, NaslovPoslovalnice, Telefon, Email, IDKraj, Aktiven FROM " + tennantDB + ".Poslovalnica"
                        cursor.execute()
                        rows = cursor.fetchall()
                        # Fixed columns → no need to read cursor.description
                        return [
                            {"IDPoslovalnica": row[0], "NazivPoslovalnice": row[1], "NaslovPoslovalnice": row[2], "Telefon": row[3], "Email": row[4], "IDKraj": row[5], "Aktiven": row[6], "NazivKraja": None}
                            for row in rows
                        ]
                    else:
                        result = response.json()
                        print(result)
                        sql = "SELECT IDPoslovalnica, NazivPoslovalnice, NaslovPoslovalnice, Telefon, Email, IDKraj, Aktiven FROM " + tennantDB + ".Poslovalnica"
                        cursor.execute(sql)
                        rows = cursor.fetchall()
                        # Fixed columns → no need to read cursor.description
                        return [
                            {"IDPoslovalnica": row[0], "NazivPoslovalnice": row[1], "NaslovPoslovalnice": row[2], "Telefon": row[3], "Email": row[4], "IDKraj": row[5], "Aktiven": row[6], "NazivKraja": result.get(str(row[5]))}
                            for row in rows
                        ]
                except Exception as e:
                    print("Prislo je do napake: ", e)
                    fail = 1
                if fail == 1:
                    sql = "SELECT IDPoslovalnica, NazivPoslovalnice, NaslovPoslovalnice, Telefon, Email, IDKraj, Aktiven FROM " + tennantDB + ".Poslovalnica"
                    cursor.execute(sql)
                    rows = cursor.fetchall()
                    # Fixed columns → no need to read cursor.description
                    return [
                        {"IDPoslovalnica": row[0], "NazivPoslovalnice": row[1], "NaslovPoslovalnice": row[2], "Telefon": row[3], "Email": row[4], "IDKraj": row[5], "Aktiven": row[6], "NazivKraja": None}
                        for row in rows
                    ]
    except Exception as e:
        print("DB error:", e)
        #raise HTTPException(status_code=500, detail="Database error")
    return {"Poslovalnica": "failed"} 

class Posl1(BaseModel):
    idposlovalnica: str
    idtennant: str
    uniqueid: str

@app.post("/poslovalnica/")
def get_poslovalnica(posl1: Posl1):

    try:
        with pool.get_connection() as conn:
            with conn.cursor() as cursor:
                #get baza poslovalnic
                query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
                cursor.execute(query,(posl1.idtennant,))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="DB not found")
                tennantDB = row[1]
                sql = "SELECT IDPoslovalnica, NazivPoslovalnice, NaslovPoslovalnice, Telefon, Email, IDKraj, Aktiven FROM " + tennantDB + ".Poslovalnica WHERE IDPoslovalnica = %s"
                cursor.execute(sql,(posl1.idposlovalnica,))

                row = cursor.fetchone()

                if row is None:
                    raise HTTPException(status_code=404, detail="Kraj not found")

                return {
                    "IDPoslovalnica": row[0],
                    "NazivPoslovalnice": row[1],
                    "NaslovPoslovalnice": row[2],
                    "Telefon": row[3],
                    "Email": row[4],
                    "IDKraj": row[5],
                    "Aktiven": row[6]
                }

    except HTTPException:
        raise
    except Exception as e:
        print("DB error:", e)
        raise HTTPException(status_code=500, detail="Database error")
    return {"Poslovalnica": "undefined"}

@app.put("/posodobiposlovalnico/")
def posodobi_poslovalnico(posl: Poslovalnica1):
    userid = posl.uniqueid
    try:
        conn = pool.get_connection()
        # Create a cursor
        cursor = conn.cursor()
        query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
        cursor.execute(query,(posl.idtennant,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="DB not found")
        tennantDB = row[1]
        if posl.aktiven != '1':
            posl.aktiven = '0'
        query = "UPDATE "+tennantDB+".Poslovalnica SET NazivPoslovalnice = %s, NaslovPoslovalnice = %s, Telefon = %s, Email = %s, IDKraj = %s, Aktiven = %s WHERE IDPoslovalnica = %s"
        cursor.execute(query,(posl.naziv,posl.naslov,posl.telefon,posl.email,posl.idkraj,posl.aktiven,posl.idposlovalnica))
        return {"Poslovalnica": "passed"}
  
    except Exception as e:
        print("Error: ", e)
        return {"Poslovalnica": "failed"}
    finally:
        cursor.close()
        conn.close() 
    return {"Poslovalnica": "unknown"}

# Konec poslovalnice

# Zacetek ponudba

# zacetek Classi

class Ponudba(BaseModel):
    idposlovalnica: str
    idstoritev: str
    idtennant: str
    uniqueid: str

class Ponu(BaseModel):
    idtennant: str
    uniqueid: str
    
class Ponu1(BaseModel):
    idponudba: str
    idtennant: str
    uniqueid: str
    
class Ponudba1(BaseModel):
    idponudba: str
    idposlovalnica: str
    idstoritev: str
    aktiven: str
    idtennant: str
    uniqueid: str

# konec Classi


@app.post("/dodajponudbo/")
def dodajPonudbo(ponudba: Ponudba):
    userid = ponudba.uniqueid
    try:
        conn = pool.get_connection()
        # Create a cursor
        cursor = conn.cursor()
        query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
        cursor.execute(query,(ponudba.idtennant,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="DB not found")
        tennantDB = row[1]

        # Preverjanje ali ponudba že obstaja!
        query = "SELECT IDPonudba, IDPoslovalnica, IDStoritev, Aktiven FROM  " + tennantDB + ".Ponuja WHERE IDPoslovalnica = %s AND IDStoritev = %s LIMIT 1"
        cursor.execute(query,(ponudba.idposlovalnica,ponudba.idstoritev))
        row = cursor.fetchone()
        print(row)
        if row is None:
            query = "INSERT INTO " + tennantDB + ".Ponuja(IDPoslovalnica,IDStoritev,Aktiven) VALUES (%s,%s,%s)"
            cursor.execute(query,(ponudba.idposlovalnica,ponudba.idstoritev,1))
            return {"Ponudba": "passed"}
        else:
            return {"Ponudba": "failed", "Opis": "ponudba že obstaja"}
        
        
  
    except Exception as e:
        print("Error: ", e)
        return {"Ponudba": "failed"}
    finally:
        cursor.close()
        conn.close() 
    return {"Ponudba": "unknown"}    
    
    
@app.post("/ponudbe/")
def get_ponudbe(ponu: Ponu):
    userid = ponu.uniqueid
    try:
        with pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # get tennant db
                query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
                cursor.execute(query,(ponu.idtennant,))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="DB not found")
                tennantDB = row[1]
                
                cursor.execute("SELECT IDStoritev FROM "+ tennantDB +".Ponuja")
                rows = cursor.fetchall()
                storitve_ids = list({
                row[0]
                for row in rows
                if row[0] is not None
                })
                print(storitve_ids)
                fail = 0
                try:
                    data = {"ids": storitve_ids, "uniqueid": ponu.uniqueid}
                    response = requests.post(f"{SERVICE_ADMVOZ_URL}/izbranestoritve/", json=data, timeout=5)
                    #response.raise_for_status()  # Raise exception for HTTP errors  
                    print(response)
                    if "application/json" not in response.headers.get("Content-Type", ""):
                        sql = "SELECT pp.IDPonudba, pp.IDPoslovalnica, pp.IDStoritev, p.NazivPoslovalnice, pp.Aktiven FROM " + tennantDB + ".Ponuja pp, " + tennantDB + ".Poslovalnica p WHERE p.IDPoslovalnica = pp.IDPoslovalnica"
                        cursor.execute()
                        rows = cursor.fetchall()
                        # Fixed columns → no need to read cursor.description
                        return [
                            {"IDPonudba": row[0], "IDPoslovalnica": row[1], "IDStoritev": row[2], "NazivPoslovalnice": row[3], "Aktiven": row[4], "NazivStoritve": None}
                            for row in rows
                        ]
                    else:
                        result = response.json()
                        print(result)
                        sql = "SELECT pp.IDPonudba, pp.IDPoslovalnica, pp.IDStoritev, p.NazivPoslovalnice, pp.Aktiven FROM " + tennantDB + ".Ponuja pp, " + tennantDB + ".Poslovalnica p WHERE p.IDPoslovalnica = pp.IDPoslovalnica"
                        cursor.execute(sql)
                        rows = cursor.fetchall()
                        # Fixed columns → no need to read cursor.description
                        return [
                            {"IDPonudba": row[0], "IDPoslovalnica": row[1], "IDStoritev": row[2], "NazivPoslovalnice": row[3], "Aktiven": row[4], "NazivStoritve": result.get(str(row[2]))}
                            for row in rows
                        ]
                except Exception as e:
                    print("Prislo je do napake: ", e)
                    fail = 1
                if fail == 1:
                    sql = "SELECT pp.IDPonudba, pp.IDPoslovalnica, pp.IDStoritev, p.NazivPoslovalnice, pp.Aktiven FROM " + tennantDB + ".Ponuja pp, " + tennantDB + ".Poslovalnica p WHERE p.IDPoslovalnica = pp.IDPoslovalnica"
                    cursor.execute(sql)
                    rows = cursor.fetchall()
                    # Fixed columns → no need to read cursor.description
                    return [
                        {"IDPonudba": row[0], "IDPoslovalnica": row[1], "IDStoritev": row[2], "NazivPoslovalnice": row[3], "Aktiven": row[4], "NazivStoritve": None}
                        for row in rows
                    ]
    except Exception as e:
        print("DB error:", e)
        #raise HTTPException(status_code=500, detail="Database error")
    return {"Ponudba": "failed"} 

class Posl1(BaseModel):
    idponudba: str
    idtennant: str
    uniqueid: str

@app.post("/ponudba/")
def get_ponudba(ponu1: Ponu1):

    try:
        with pool.get_connection() as conn:
            with conn.cursor() as cursor:
                #get baza poslovalnic
                query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
                cursor.execute(query,(ponu1.idtennant,))
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="DB not found")
                tennantDB = row[1]
                
                sql = "SELECT IDPonudba, IDPoslovalnica, IDStoritev, Aktiven FROM " + tennantDB + ".Ponuja WHERE IDPonudbe = %s"
                cursor.execute(sql,(ponu1.idponudba,))

                row = cursor.fetchone()

                if row is None:
                    raise HTTPException(status_code=404, detail="Kraj not found")

                return {
                    "IDPonudba": row[0],
                    "IDPoslovalnica": row[1],
                    "IDStoritev": row[2],
                    "Aktiven": row[3]
                }

    except HTTPException:
        raise
    except Exception as e:
        print("DB error:", e)
        raise HTTPException(status_code=500, detail="Database error")
    return {"Ponudba": "undefined"}

@app.put("/posodobiponudbo/")
def posodobi_ponudbo(ponu: Ponudba1):
    userid = ponu.uniqueid
    try:
        conn = pool.get_connection()
        # Create a cursor
        cursor = conn.cursor()
        query = "SELECT IDTennant, TennantDBPoslovalnice FROM  " + adminbaza + ".TennantLookup WHERE IDTennant = %s"
        cursor.execute(query,(ponu.idtennant,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="DB not found")
        tennantDB = row[1]
        
        if ponu.aktiven != '1':
            ponu.aktiven = '0'
        query = "SELECT IDPonudba, IDPoslovalnica, IDStoritev, Aktiven FROM  " + tennantDB + ".Ponuja WHERE IDPoslovalnica = %s AND IDStoritev = %s LIMIT 1"
        cursor.execute(query,(ponu.idposlovalnica,ponu.idstoritev))
        row = cursor.fetchone()
        print(row)
        if row is None:
            query = "UPDATE "+tennantDB+".Ponuja SET IDPoslovalnica = %s, IDStoritev = %s, Aktiven = %s WHERE IDPonudba = %s"
            cursor.execute(query,(ponu.idposlovalnica,ponu.idstoritev,ponu.aktiven,ponu.idponudba))
            return {"Ponudba": "passed"}
        else:
            return {"Ponudba": "failed", "Opis": "ponudba s posodobljenimi vrednostmi že obstaja!"}
  
    except Exception as e:
        print("Error: ", e)
        return {"Ponudba": "failed"}
    finally:
        cursor.close()
        conn.close() 
    return {"Ponudba": "unknown"}


# Konec ponudba




    
