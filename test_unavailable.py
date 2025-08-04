#!/usr/bin/env python3
"""
Script de test pour simuler des fichiers indisponibles
"""
import sqlite3
import sys
import os

# Ajouter le chemin du projet
sys.path.append('/home/kesurof/Projet_Gihtub/Redriva/src')

DB_PATH = '/home/kesurof/Projet_Gihtub/Redriva/data/redriva.db'

def test_unavailable_files():
    """Simule quelques fichiers indisponibles pour tester le système"""
    
    # Connexion à la base de données
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Vérifier les torrents existants
        c.execute("SELECT id, name FROM torrent_details LIMIT 2")
        torrents = c.fetchall()
        
        if not torrents:
            print("❌ Aucun torrent trouvé dans la base pour les tests")
            return
        
        # Simuler des erreurs sur les 2 premiers torrents
        test_errors = [
            ('503_service_unavailable', 'Simulated 503 error for testing'),
            ('404_file_not_found', 'Simulated 404 error for testing')
        ]
        
        for i, (torrent_id, name) in enumerate(torrents):
            if i < len(test_errors):
                error_code, error_msg = test_errors[i]
                
                c.execute("""
                    UPDATE torrent_details 
                    SET error = ?, status = 'error' 
                    WHERE id = ?
                """, (error_msg, torrent_id))
                
                print(f"✅ Simulé erreur {error_code} pour torrent: {name}")
        
        conn.commit()
        print(f"🎯 Test configuré: {len(test_errors)} fichiers marqués comme indisponibles")

def reset_test():
    """Réinitialise les erreurs de test"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute("""
            UPDATE torrent_details 
            SET error = NULL, status = 'downloaded' 
            WHERE error LIKE '%Simulated%'
        """)
        
        changed = c.rowcount
        conn.commit()
        print(f"🔄 Réinitialisé: {changed} torrents nettoyés")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'reset':
        reset_test()
    else:
        test_unavailable_files()
        print("\n📋 Pour tester:")
        print("1. Allez sur http://127.0.0.1:5000")
        print("2. Vérifiez la carte 'Fichiers indisponibles' sur le dashboard")
        print("3. Cliquez sur 'Gérer les indisponibles' pour voir les torrents filtrés")
        print("4. Testez le bouton 'Vérifier santé fichiers' dans l'onglet Actions")
        print("5. Testez le bouton 'Nettoyer indisponibles' dans l'onglet Actions")
        print("\n🔄 Pour réinitialiser: python test_unavailable.py reset")
