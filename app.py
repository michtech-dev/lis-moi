import asyncio
import io
import os
import re

import edge_tts
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from google.auth.transport import requests as grequests
from google.oauth2 import id_token

app = Flask(__name__)
CORS(app)

MAX_CARACTERES = 30000
VOIX_PAR_DEFAUT = "fr-FR-DeniseNeural"
# Identifiant du projet Firebase (à définir dans les variables du Space)
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "")


def utilisateur_connecte():
    if not FIREBASE_PROJECT_ID:
        return True  # connexion non configurée côté serveur
    entete = request.headers.get("Authorization", "")
    if not entete.startswith("Bearer "):
        return False
    try:
        id_token.verify_firebase_token(
            entete[7:], grequests.Request(), audience=FIREBASE_PROJECT_ID
        )
        return True
    except Exception:
        return False


async def fabriquer(texte, voix, vitesse):
    com = edge_tts.Communicate(texte, voix, rate=vitesse)
    tampon = io.BytesIO()
    async for morceau in com.stream():
        if morceau["type"] == "audio":
            tampon.write(morceau["data"])
    tampon.seek(0)
    return tampon


@app.get("/")
def accueil():
    return "Le serveur audio fonctionne."


@app.post("/tts")
def tts():
    if not utilisateur_connecte():
        return jsonify(erreur="Connexion requise."), 401
    donnees = request.get_json(silent=True) or {}
    texte = (donnees.get("text") or "").strip()
    voix = donnees.get("voice") or VOIX_PAR_DEFAUT
    vitesse = donnees.get("rate") or "+0%"

    if not texte:
        return jsonify(erreur="Le texte est vide."), 400
    if len(texte) > MAX_CARACTERES:
        return jsonify(erreur="Texte trop long (maximum %d caractères)." % MAX_CARACTERES), 413
    if not re.fullmatch(r"[a-z]{2,3}-[A-Z]{2,4}-[A-Za-z]+Neural", voix):
        voix = VOIX_PAR_DEFAUT
    if not re.fullmatch(r"[+-]\d{1,3}%", vitesse):
        vitesse = "+0%"

    try:
        tampon = asyncio.run(fabriquer(texte, voix, vitesse))
    except Exception:
        return jsonify(erreur="La création de l'audio a échoué. Réessayez."), 502

    return send_file(tampon, mimetype="audio/mpeg", as_attachment=True, download_name="audio.mp3")
