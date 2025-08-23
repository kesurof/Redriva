#!/usr/bin/env python3
"""
Arr Monitor - Script de compatibilité pour l'intégration Redriva
Ce script utilise maintenant le module de surveillance intégré à Redriva

MIGRATION VERS REDRIVA:
- La surveillance Arr est maintenant intégrée dans Redriva (src/arr_monitor.py)
- Ce script sert de point d'entrée CLI pour la compatibilité
- Configuration centralisée via config/config.json de Redriva
- Logs unifiés avec le système Redriva
- Interface web disponible sur /arr-monitor
"""

import os
import sys
import argparse
import logging

# Ajouter le répertoire src au path pour importer les modules Redriva
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    parser = argparse.ArgumentParser(
        description="Arr Monitor - Surveillance Sonarr/Radarr (intégré à Redriva)",
        epilog="MIGRATION: Ce script utilise maintenant l'intégration Redriva. "
               "Utilisez l'interface web /arr-monitor pour une gestion complète."
    )
    parser.add_argument('--test', '-t', action='store_true', 
                       help='Exécuter un seul cycle de test')
    parser.add_argument('--debug', '-d', action='store_true', 
                       help='Mode debug (logs verbeux)')
    parser.add_argument('--diagnose', action='store_true', 
                       help='Mode diagnostic complet de la queue')
    parser.add_argument('--status', action='store_true',
                       help='Afficher le statut de la surveillance')
    parser.add_argument('--start', action='store_true',
                       help='Démarrer la surveillance continue')
    parser.add_argument('--stop', action='store_true',
                       help='Arrêter la surveillance continue')
    parser.add_argument('--interval', type=int, default=300,
                       help='Intervalle en secondes pour la surveillance (défaut: 300)')
    
    args = parser.parse_args()
    
    # Configuration du logging
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Import des modules Redriva
        from config_manager import ConfigManager
        from arr_monitor import get_arr_monitor
        
        logger.info("🔧 Arr Monitor - Version intégrée Redriva")
        logger.info("📱 Interface web disponible: http://localhost:5000/arr-monitor")
        
        # Initialiser le gestionnaire de configuration et le moniteur
        config_manager = ConfigManager()
        monitor = get_arr_monitor(config_manager)
        
        # Vérifier la configuration
        sonarr_config = monitor.get_sonarr_config()
        radarr_config = monitor.get_radarr_config()
        
        if not sonarr_config and not radarr_config:
            logger.error("❌ Aucune application Arr configurée dans config/config.json")
            logger.info("💡 Configurez Sonarr/Radarr via l'interface web /settings")
            return 1
        
        # Traitement selon les arguments
        if args.status:
            # Afficher le statut
            status = monitor.get_status()
            logger.info(f"📊 Statut de la surveillance:")
            logger.info(f"   En cours: {'✅ Oui' if status['running'] else '❌ Non'}")
            logger.info(f"   Sonarr: {'✅ Activé' if status['sonarr_enabled'] else '❌ Désactivé'}")
            logger.info(f"   Radarr: {'✅ Activé' if status['radarr_enabled'] else '❌ Désactivé'}")
            logger.info(f"   Version: {status['version']}")
            
        elif args.start:
            # Démarrer la surveillance
            if monitor.start_monitoring(args.interval):
                logger.info(f"🚀 Surveillance démarrée (intervalle: {args.interval}s)")
                logger.info("🛑 Appuyez sur Ctrl+C pour arrêter")
                try:
                    while monitor.get_status()['running']:
                        import time
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("🛑 Interruption reçue, arrêt...")
                    monitor.stop_monitoring()
            else:
                logger.error("❌ Échec du démarrage (surveillance déjà en cours?)")
                return 1
                
        elif args.stop:
            # Arrêter la surveillance
            if monitor.stop_monitoring():
                logger.info("🛑 Surveillance arrêtée")
            else:
                logger.warning("⚠️ Surveillance déjà arrêtée")
                
        elif args.diagnose:
            # Mode diagnostic
            logger.info("🔬 Mode diagnostic...")
            
            if sonarr_config:
                logger.info("📺 Diagnostic Sonarr:")
                sonarr_diag = monitor.diagnose_queue('sonarr')
                if 'error' in sonarr_diag:
                    logger.error(f"   Erreur: {sonarr_diag['error']}")
                else:
                    logger.info(f"   Total: {sonarr_diag['total_items']} éléments")
                    logger.info(f"   Erreurs: {sonarr_diag['errors_detected']}")
                    if sonarr_diag['error_items']:
                        logger.info("   Éléments en erreur:")
                        for item in sonarr_diag['error_items'][:5]:  # Afficher max 5
                            logger.info(f"     - {item['title']}: {item['errorMessage']}")
            
            if radarr_config:
                logger.info("🎬 Diagnostic Radarr:")
                radarr_diag = monitor.diagnose_queue('radarr')
                if 'error' in radarr_diag:
                    logger.error(f"   Erreur: {radarr_diag['error']}")
                else:
                    logger.info(f"   Total: {radarr_diag['total_items']} éléments")
                    logger.info(f"   Erreurs: {radarr_diag['errors_detected']}")
                    if radarr_diag['error_items']:
                        logger.info("   Éléments en erreur:")
                        for item in radarr_diag['error_items'][:5]:  # Afficher max 5
                            logger.info(f"     - {item['title']}: {item['errorMessage']}")
                            
        elif args.test:
            # Mode test - un seul cycle
            logger.info("🧪 Mode test - cycle unique")
            results = monitor.run_cycle()
            
            total_corrections = sum(results.values())
            logger.info(f"✅ Cycle terminé - {total_corrections} corrections appliquées")
            
            for app_name, corrections in results.items():
                if corrections > 0:
                    logger.info(f"   {app_name}: {corrections} corrections")
                else:
                    logger.info(f"   {app_name}: Aucune erreur détectée")
                    
        else:
            # Mode par défaut - afficher l'aide et le statut
            parser.print_help()
            print("\n" + "="*60)
            print("MIGRATION VERS REDRIVA:")
            print("- Configuration: config/config.json (section sonarr/radarr)")
            print("- Interface web: http://localhost:5000/arr-monitor")
            print("- Logs intégrés au système Redriva")
            print("="*60)
            
            # Afficher le statut si disponible
            try:
                status = monitor.get_status()
                print(f"\nStatut actuel:")
                print(f"  Surveillance: {'En cours' if status['running'] else 'Arrêtée'}")
                print(f"  Sonarr: {'Activé' if status['sonarr_enabled'] else 'Désactivé'}")
                print(f"  Radarr: {'Activé' if status['radarr_enabled'] else 'Désactivé'}")
            except Exception:
                pass
        
    except ImportError as e:
        logger.error(f"❌ Modules Redriva non trouvés: {e}")
        logger.error("💡 Assurez-vous d'exécuter ce script depuis le répertoire Redriva")
        return 1
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
