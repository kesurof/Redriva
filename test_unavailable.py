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

def diagnose_real_errors():
    """Diagnostique les vraies erreurs présentes dans la base"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Vérifier toutes les erreurs existantes
        c.execute("""
            SELECT error, COUNT(*) as count 
            FROM torrent_details 
            WHERE error IS NOT NULL 
            GROUP BY error 
            ORDER BY count DESC
        """)
        errors = c.fetchall()
        
        print("🔍 DIAGNOSTIC DES ERREURS RÉELLES:")
        if errors:
            for error, count in errors:
                print(f"   📋 {error}: {count} torrents")
        else:
            print("   ✅ Aucune erreur trouvée dans la base")
        
        # Vérifier les statuts
        c.execute("""
            SELECT status, COUNT(*) as count 
            FROM torrent_details 
            WHERE status IS NOT NULL 
            GROUP BY status 
            ORDER BY count DESC
        """)
        statuses = c.fetchall()
        
        print("\n📊 RÉPARTITION DES STATUTS:")
        for status, count in statuses:
            print(f"   📌 {status}: {count} torrents")

def test_unavailable_files():
    """Simule quelques fichiers indisponibles pour tester le système"""
    
    # D'abord diagnostiquer les erreurs réelles
    diagnose_real_errors()
    
    # Connexion à la base de données
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Vérifier les torrents existants
        c.execute("SELECT id, name FROM torrent_details LIMIT 2")
        torrents = c.fetchall()
        
        if not torrents:
            print("❌ Aucun torrent trouvé dans la base pour les tests")
            return
        
        # Simuler des erreurs avec des formats qui matchent les critères de recherche
        test_errors = [
            ('rd_error_24_unavailable_file', 'Real-Debrid API error: unavailable_file (code 24)'),
            ('rd_error_503_service_unavailable', 'Real-Debrid API error: service unavailable (code 503)')
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
            WHERE error LIKE '%Real-Debrid API error:%' OR error LIKE '%rd_error_%'
        """)
        
        changed = c.rowcount
        conn.commit()
        print(f"🔄 Réinitialisé: {changed} torrents nettoyés")

def inject_real_rd_error():
    """Injecte une vraie erreur au format Real-Debrid API"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Prendre le premier torrent disponible
        c.execute("SELECT id, name FROM torrent_details WHERE status = 'downloaded' LIMIT 1")
        torrent = c.fetchone()
        
        if not torrent:
            print("❌ Aucun torrent disponible pour injection d'erreur")
            return
        
        torrent_id, name = torrent
        
        # Injecter une erreur au format Real-Debrid exact
        real_error = "rd_error_24_unavailable_file"
        
        c.execute("""
            UPDATE torrent_details 
            SET error = ?, status = 'error' 
            WHERE id = ?
        """, (real_error, torrent_id))
        
        conn.commit()
        print(f"✅ Injecté erreur Real-Debrid sur: {name}")
        print(f"   Format: {real_error}")
        
        return torrent_id

if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == 'reset':
            reset_test()
        elif action == 'diagnose':
            diagnose_real_errors()
        elif action == 'inject':
            inject_real_rd_error()
        else:
            print("❌ Action inconnue. Utilisez: diagnose, inject, reset, ou aucun argument pour le test")
    else:
        test_unavailable_files()
        print("\n📋 Pour tester:")
        print("1. Allez sur http://127.0.0.1:5000")
        print("2. Vérifiez la carte 'Fichiers indisponibles' sur le dashboard")
        print("3. Cliquez sur 'Gérer les indisponibles' pour voir les torrents filtrés")
        print("4. Testez le bouton 'Vérifier santé fichiers' dans l'onglet Actions")
        print("5. Testez le bouton 'Nettoyer indisponibles' dans l'onglet Actions")
        print("\n� Commandes disponibles:")
        print("  python test_unavailable.py diagnose  # Voir les vraies erreurs")
        print("  python test_unavailable.py inject    # Injecter une vraie erreur RD")
        print("  python test_unavailable.py reset     # Nettoyer les erreurs de test")
