from configparser import ConfigParser

def convert_campaign_strings(template_file, target_file):
    """Convertit le fichier campaignstrings.txt pour correspondre au format du template"""
    # Lire et parser le template
    template_cfg = ConfigParser(allow_no_value=True, strict=False)
    template_cfg.optionxform = str  # préserver la casse
    with open(template_file, 'r', encoding='utf-8') as f:
        template_cfg.read_file(f)
    
    # Lire et parser le fichier cible en gérant le BOM
    trans_cfg = ConfigParser(allow_no_value=True, strict=False)
    trans_cfg.optionxform = str  # préserver la casse
    with open(target_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig gère le BOM
        trans_cfg.read_file(f)
    
    # Créer une nouvelle config pour la sortie
    output_cfg = ConfigParser(allow_no_value=True, strict=False)
    output_cfg.optionxform = str
    
    # Traiter chaque section du template
    for section in template_cfg.sections():
        if not output_cfg.has_section(section):
            output_cfg.add_section(section)
            
        # Copier toutes les clés du template vers la sortie
        for key in template_cfg[section]:
            output_cfg[section][key] = template_cfg[section][key]
            
        # Si la section existe dans la traduction, appliquer les traductions
        if trans_cfg.has_section(section):
            # Copier Header et Name depuis la traduction
            for key in ['Header', 'Name']:
                if trans_cfg.has_option(section, key):
                    output_cfg[section][key] = trans_cfg[section][key]
            
            # Traiter les cinématiques
            cinematic_mapping = {
                'IntroCinematic': 'InCinematic',
                'OpenCinematic': 'OpCinematic',
                'EndCinematic': 'EdCinematic'
            }
            
            for template_key, trans_key in cinematic_mapping.items():
                if (template_cfg.has_option(section, template_key) and 
                    trans_cfg.has_option(section, trans_key)):
                    
                    # Extraire les parties du template
                    template_value = template_cfg[section][template_key]
                    if template_value.strip() == '':
                        # Gérer les valeurs vides
                        new_value = ''
                    else:
                        template_parts = [part.strip('" ') for part in template_value.split(',')]
                        
                        if len(template_parts) < 3:
                            # Format invalide, conserver l'original
                            new_value = template_value
                        else:
                            # Récupérer le nom traduit
                            trans_name = trans_cfg[section][trans_key].strip('"')
                            # Reconstruire avec le nom traduit
                            new_value = f'"{template_parts[0]}","{trans_name}","{template_parts[2]}"'
                    
                    output_cfg[section][template_key] = new_value
            
            # Traiter les missions
            mission_keys = [k for k in template_cfg[section] if k.startswith('Mission')]
            for mission_key in mission_keys:
                # Extraire le numéro de mission
                mission_num = mission_key[7:]
                
                # Clés correspondantes dans la traduction
                title_key = f'Title{mission_num}'
                mission_name_key = f'Mission{mission_num}'
                
                # Vérifier si les clés de traduction existent
                has_title = trans_cfg.has_option(section, title_key)
                has_mission_name = trans_cfg.has_option(section, mission_name_key)
                
                if has_title and has_mission_name:
                    # Extraire les parties du template
                    template_value = template_cfg[section][mission_key]
                    template_parts = [part.strip('" ') for part in template_value.split(',')]
                    
                    if len(template_parts) >= 3:
                        # Récupérer le titre et le nom traduits
                        trans_title = trans_cfg[section][title_key].strip('"')
                        trans_name = trans_cfg[section][mission_name_key].strip('"')
                        
                        # Reconstruire avec les traductions
                        new_value = f'"{trans_title}","{trans_name}","{template_parts[2]}"'
                        output_cfg[section][mission_key] = new_value
    
    # Écrire le résultat dans le fichier cible
    with open(target_file, 'w', encoding='utf-8') as f:
        for section in output_cfg.sections():
            f.write(f'[{section}]\n')
            for key, value in output_cfg[section].items():
                if value is None:
                    f.write(f'{key}\n')
                else:
                    f.write(f'{key}={value}\n')
            f.write('\n')