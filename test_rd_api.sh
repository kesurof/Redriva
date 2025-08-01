#!/bin/bash

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Test de l'API Real-Debrid${NC}"
echo "=================================="

source config/.env 2>/dev/null || echo "Pas de fichier .env trouvé"

# Vérification du token
if [ -z "$RD_TOKEN" ]; then
    echo -e "${RED}❌ Variable RD_TOKEN non définie${NC}"
    echo "Exportez votre token : export RD_TOKEN=\"votre_token\""
    exit 1
fi

echo -e "${BLUE}📋 Étape 1: Test du token...${NC}"
USER_INFO=$(curl -s -H "Authorization: Bearer $RD_TOKEN" \
                 "https://api.real-debrid.com/rest/1.0/user")

if echo "$USER_INFO" | jq -e .username > /dev/null 2>&1; then
    USERNAME=$(echo "$USER_INFO" | jq -r .username)
    POINTS=$(echo "$USER_INFO" | jq -r .points)
    echo -e "${GREEN}✅ Token valide - Utilisateur: $USERNAME (Points: $POINTS)${NC}"
else
    echo -e "${RED}❌ Token invalide${NC}"
    echo "$USER_INFO"
    exit 1
fi

echo -e "\n${BLUE}📋 Étape 2: Récupération des torrents...${NC}"
TORRENTS=$(curl -s -H "Authorization: Bearer $RD_TOKEN" \
                "https://api.real-debrid.com/rest/1.0/torrents")

TORRENT_COUNT=$(echo "$TORRENTS" | jq length)
echo -e "${GREEN}✅ $TORRENT_COUNT torrents trouvés${NC}"

if [ "$TORRENT_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}📊 Status des torrents:${NC}"
    echo "$TORRENTS" | jq -r '.[] | "\(.status): \(.filename[0:50])..."' | head -5
    
    # Prendre le premier torrent avec le status "downloaded"
    TORRENT_ID=$(echo "$TORRENTS" | jq -r '.[] | select(.status == "downloaded") | .id' | head -1)
    
    if [ "$TORRENT_ID" != "null" ] && [ -n "$TORRENT_ID" ]; then
        echo -e "${GREEN}✅ Torrent téléchargé trouvé: $TORRENT_ID${NC}"
        
        echo -e "\n${BLUE}📋 Étape 3: Détails du torrent $TORRENT_ID...${NC}"
        TORRENT_INFO=$(curl -s -H "Authorization: Bearer $RD_TOKEN" \
                           "https://api.real-debrid.com/rest/1.0/torrents/info/$TORRENT_ID")
        
        echo -e "${YELLOW}📊 Informations du torrent:${NC}"
        echo "$TORRENT_INFO" | jq '{filename: .filename, status: .status, progress: .progress, files_count: (.files | length), links_count: (.links | length)}'
        
        # Récupérer le premier lien disponible
        FILE_LINK=$(echo "$TORRENT_INFO" | jq -r '.links[0] // empty')
        
        if [ -n "$FILE_LINK" ] && [ "$FILE_LINK" != "null" ]; then
            echo -e "${GREEN}✅ Lien trouvé: ${FILE_LINK:0:80}...${NC}"
            
            echo -e "\n${BLUE}📋 Étape 4: Débridage du lien...${NC}"
            UNRESTRICT_RESULT=$(curl -s -X POST \
                                   -H "Authorization: Bearer $RD_TOKEN" \
                                   -d "link=$FILE_LINK" \
                                   "https://api.real-debrid.com/rest/1.0/unrestrict/link")
            
            echo -e "${YELLOW}📊 Résultat du débridage:${NC}"
            echo "$UNRESTRICT_RESULT" | jq '{filename: .filename, download: .download[0:80], mimeType: .mimeType, filesize: .filesize, id: .id}'
            
            # Extraire l'ID pour les métadonnées
            FILE_ID=$(echo "$UNRESTRICT_RESULT" | jq -r '.id // empty')
            
            if [ -n "$FILE_ID" ] && [ "$FILE_ID" != "null" ]; then
                echo -e "${GREEN}✅ File ID obtenu: $FILE_ID${NC}"
                
                echo -e "\n${BLUE}📋 Étape 5: Test métadonnées média (/streaming/mediaInfos)...${NC}"
                MEDIA_INFO=$(curl -s -H "Authorization: Bearer $RD_TOKEN" \
                                "https://api.real-debrid.com/rest/1.0/streaming/mediaInfos/$FILE_ID")
                
                # Vérifier si la réponse contient une erreur
                if echo "$MEDIA_INFO" | jq -e .error > /dev/null 2>&1; then
                    echo -e "${RED}❌ Erreur API:${NC}"
                    echo "$MEDIA_INFO" | jq .error
                elif echo "$MEDIA_INFO" | jq -e .filename > /dev/null 2>&1; then
                    echo -e "${GREEN}✅ Métadonnées récupérées avec succès!${NC}"
                    echo -e "${YELLOW}📊 Résumé des métadonnées:${NC}"
                    echo "$MEDIA_INFO" | jq '{
                        filename: .filename,
                        type: .type,
                        duration: .duration,
                        size: .size,
                        hoster: .hoster,
                        video_count: (.details.video // {} | length),
                        audio_count: (.details.audio // {} | length),
                        subtitle_count: (.details.subtitles // {} | length)
                    }'
                    
                    echo -e "\n${YELLOW}📊 Détails vidéo:${NC}"
                    echo "$MEDIA_INFO" | jq '.details.video // {} | to_entries[] | {lang: .value.lang, codec: .value.codec, resolution: "\(.value.width)x\(.value.height)"}'
                    
                    echo -e "\n${YELLOW}📊 Détails audio:${NC}"
                    echo "$MEDIA_INFO" | jq '.details.audio // {} | to_entries[] | {lang: .value.lang, codec: .value.codec, channels: .value.channels}'
                    
                    echo -e "\n${YELLOW}📊 Sous-titres:${NC}"
                    echo "$MEDIA_INFO" | jq '.details.subtitles // {} | to_entries[] | {lang: .value.lang, type: .value.type}'
                    
                else
                    echo -e "${RED}❌ Réponse inattendue:${NC}"
                    echo "$MEDIA_INFO"
                fi
            else
                echo -e "${RED}❌ Aucun File ID trouvé dans la réponse de débridage${NC}"
            fi
        else
            echo -e "${RED}❌ Aucun lien trouvé dans le torrent${NC}"
            echo -e "${YELLOW}📊 Structure du torrent:${NC}"
            echo "$TORRENT_INFO" | jq '{files: [.files[]? | {selected}], links: .links}'
        fi
    else
        echo -e "${RED}❌ Aucun torrent téléchargé trouvé${NC}"
        echo -e "${YELLOW}📊 Premiers torrents disponibles:${NC}"
        echo "$TORRENTS" | jq '.[0:3] | .[] | {id, filename: .filename[0:50], status}'
    fi
else
    echo -e "${RED}❌ Aucun torrent trouvé${NC}"
fi

echo -e "\n${BLUE}📋 Test terminé!${NC}"
