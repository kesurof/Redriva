#!/usr/bin/env python3
"""
Test script pour vérifier le format de sortie de sync_torrents_only
"""
import sys
import os
sys.path.append('src')

from main import get_status_emoji
import sqlite3

# Test de la fonction get_status_emoji
print("📊 Test des emojis de statut:")
test_statuses = ['downloaded', 'downloading', 'error', 'deleted', 'queued', 'waiting']
for status in test_statuses:
    emoji = get_status_emoji(status)
    print(f"   {emoji} {status}")

# Test de format de sortie comme dans sync_torrents_only
print(f"\n📊 Résumé des torrents synchronisés:")
# Simulation des données
fake_stats = {
    'downloaded': 4537,
    'downloading': 17, 
    'error': 38,
    'deleted': 14
}

for status, count in fake_stats.items():
    emoji = get_status_emoji(status)
    print(f"   {emoji} {status}: {count}")

print("\n✅ Test du format réussi !")
