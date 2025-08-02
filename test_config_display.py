#!/usr/bin/env python3
"""
Script de test pour vérifier l'affichage de la configuration dans l'interface web
"""

import sqlite3
import json
import requests
from urllib.parse import urljoin

def test_database_config():
    """Teste la lecture directe de la configuration depuis la base de données"""
    print("🔍 Test lecture configuration base de données...")
    
    try:
        conn = sqlite3.connect('/home/kesurof/Projet_Gihtub/Redriva/data/symlink.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM symlink_config")
        config_row = cursor.fetchone()
        
        if config_row:
            # Récupérer les noms des colonnes
            columns = [description[0] for description in cursor.description]
            config_dict = dict(zip(columns, config_row))
            
            print("✅ Configuration trouvée dans la DB:")
            for key, value in config_dict.items():
                print(f"   {key}: {value}")
            
            return config_dict
        else:
            print("❌ Aucune configuration trouvée dans la DB")
            return None
            
    except Exception as e:
        print(f"❌ Erreur lecture DB: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def test_api_config():
    """Teste l'API de récupération de configuration"""
    print("\n🌐 Test API de configuration...")
    
    try:
        # Test de l'endpoint de configuration
        response = requests.get('http://localhost:5000/api/symlink/config')
        
        if response.status_code == 200:
            config = response.json()
            print("✅ API configuration accessible:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {json.dumps(config, indent=2)}")
            return config
        else:
            print(f"❌ Erreur API: Status {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur connexion API: {e}")
        return None

def test_web_interface():
    """Teste l'accès à l'interface web"""
    print("\n🌐 Test interface web...")
    
    try:
        response = requests.get('http://localhost:5000/symlink')
        
        if response.status_code == 200:
            print("✅ Interface web accessible")
            print(f"   Status Code: {response.status_code}")
            
            # Vérifier la présence d'éléments clés dans le HTML
            html = response.text
            checks = [
                ('symlink_tool.js', 'symlink_tool.js' in html),
                ('Configuration tab', 'id="settings-tab"' in html),
                ('Media path input', 'id="media-path"' in html),
                ('Sonarr config', 'id="sonarr-host"' in html),
                ('Radarr config', 'id="radarr-host"' in html)
            ]
            
            for check_name, result in checks:
                status = "✅" if result else "❌"
                print(f"   {status} {check_name}")
                
            return True
        else:
            print(f"❌ Erreur interface web: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur connexion interface: {e}")
        return False

def main():
    print("🧪 Test d'affichage de configuration - Symlink Manager")
    print("=" * 60)
    
    # Test 1: Base de données
    db_config = test_database_config()
    
    # Test 2: API
    api_config = test_api_config()
    
    # Test 3: Interface web
    web_ok = test_web_interface()
    
    # Résumé
    print("\n📊 RÉSUMÉ DES TESTS:")
    print("=" * 60)
    
    if db_config:
        print("✅ Configuration présente dans la base de données")
    else:
        print("❌ Problème avec la base de données")
    
    if api_config:
        print("✅ API de configuration fonctionnelle")
    else:
        print("❌ Problème avec l'API")
    
    if web_ok:
        print("✅ Interface web accessible")
    else:
        print("❌ Problème avec l'interface web")
    
    # Instructions pour le test manuel
    print("\n🔧 INSTRUCTIONS POUR TEST MANUEL:")
    print("1. Ouvrez http://localhost:5000/symlink")
    print("2. Cliquez sur l'onglet 'Configuration'")
    print("3. Vérifiez que les champs sont pré-remplis avec vos données")
    print("4. Si les champs sont vides, ouvrez la console du navigateur (F12)")
    print("5. Rechargez la page et vérifiez les erreurs JavaScript")

if __name__ == "__main__":
    main()
