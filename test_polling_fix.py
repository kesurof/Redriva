#!/usr/bin/env python3
"""
Test du système de polling après correction du conflit
"""
import requests
import time
import json

def test_polling_fixed():
    base_url = "http://127.0.0.1:5000"
    
    print("🔍 Test du système de polling corrigé...")
    
    # Test des API
    endpoints = ["/api/health", "/api/task_status"]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {endpoint} - OK")
                if endpoint == "/api/task_status":
                    print(f"   📊 Running: {data.get('running', False)}")
                    print(f"   📊 Detailed result: {data.get('detailed_result') is not None}")
            else:
                print(f"❌ {endpoint} - ERROR ({response.status_code})")
        except Exception as e:
            print(f"❌ {endpoint} - {str(e)}")
    
    print(f"\n🔄 Test de polling continu (15 secondes)...")
    start_time = time.time()
    success_count = 0
    error_count = 0
    
    while time.time() - start_time < 15:
        try:
            response = requests.get(f"{base_url}/api/task_status", timeout=2)
            if response.status_code == 200:
                success_count += 1
                print("✅", end="", flush=True)
            else:
                error_count += 1
                print("❌", end="", flush=True)
        except:
            error_count += 1
            print("🔌", end="", flush=True)
        
        time.sleep(1)
    
    print(f"\n📊 Résultats: {success_count} succès, {error_count} erreurs")
    if error_count == 0:
        print("🎉 Polling fonctionnel - Pas d'erreurs NetworkError !")
    else:
        print(f"⚠️ {error_count} erreurs détectées")
    
    return error_count == 0

if __name__ == "__main__":
    success = test_polling_fixed()
    if success:
        print("\n✅ Système corrigé avec succès !")
        print("🌐 Vous pouvez maintenant utiliser l'interface sans erreurs de polling")
    else:
        print("\n❌ Des problèmes persistent")
