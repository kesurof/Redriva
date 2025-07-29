# Guide de contribution

Merci de votre intérêt pour contribuer à Redriva ! 🎉

## 🚀 Démarrage rapide

1. **Fork** le projet
2. **Clonez** votre fork :
   ```bash
   git clone https://github.com/votre-username/Redriva.git
   cd Redriva
   ```
3. **Installez** les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
4. **Configurez** votre token de test :
   ```bash
   cp .env.example .env
   # Éditez .env avec votre token Real-Debrid
   ```

## 🛠️ Développement

### Structure du projet
```
Redriva/
├── src/main.py          # Script principal
├── config/              # Configuration (ignoré par Git)
├── data/               # Base de données locale (ignoré par Git)
├── .env.example        # Modèle de configuration
└── requirements.txt    # Dépendances Python
```

### Tests
Avant de soumettre votre contribution :
```bash
# Test de base
python src/main.py --stats

# Test avec un petit échantillon
python src/main.py --torrents-only
```

## 📝 Types de contributions

- 🐛 **Corrections de bugs**
- ⚡ **Améliorations de performances**
- 📚 **Amélioration de la documentation**
- ✨ **Nouvelles fonctionnalités**

## 🔀 Processus de contribution

1. Créez une **branche** pour votre fonctionnalité :
   ```bash
   git checkout -b feature/ma-super-feature
   ```
2. **Commitez** vos changements :
   ```bash
   git commit -m "feat: ajoute ma super feature"
   ```
3. **Poussez** vers votre fork :
   ```bash
   git push origin feature/ma-super-feature
   ```
4. Ouvrez une **Pull Request**

## 📋 Checklist avant PR

- [ ] Le code fonctionne sans erreur
- [ ] Les messages de commit sont clairs
- [ ] La documentation est mise à jour si nécessaire
- [ ] Aucun token ou donnée sensible dans le commit

## 🤝 Code de conduite

- Soyez respectueux et constructifs
- Testez vos modifications avant de les soumettre
- Documentez les changements complexes
- Ne jamais inclure de tokens ou données personnelles

Merci de contribuer à Redriva ! 🚀
