#!/usr/bin/env python3
"""
Extractor de Contenido del Sistema Asistente IA
Consolida todos los archivos en un solo archivo de salida
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

class ExtractorSistema:
    def __init__(self, directorio_base="."):
        self.directorio_base = Path(directorio_base).resolve()
        self.archivos_ignorar = {
            '.git', '__pycache__', 'venv', 'env', '.env',
            '*.pyc', '*.pyo', '*.pyd', '.DS_Store', '*.log',
            'interacciones.log', 'output_completo.txt'
        }
        
        # Archivos a extraer (ordenados por importancia)
        self.archivos_objetivo = [
            # Archivos principales
            'app.py',
            'foro.py',
            'curso.py',
            'mejorar.py',
            'MARCO_ETICO.txt',
            'README.md',
            
            # Archivos de configuración
            'sql_base.json',
            'sql_ejemplos.json',
            
            # Templates HTML
            'templates/foro_chat.html',
            'templates/mejorar.html',
            
            # JavaScript
            'static/app.js',
            'static/mejorar.js',
            'static/state.js',
            'static/ui.js',
            
            # CSS
            'static/foro_chat.css',
            'static/mejorar.css',
            
            # Assets
            'static/logo_hospital.png',
            'static/logo_openlab.png'
        ]

    def debe_ignorar(self, ruta):
        """Verifica si un archivo/directorio debe ser ignorado"""
        nombre = ruta.name
        for patron in self.archivos_ignorar:
            if patron.startswith('*'):
                if nombre.endswith(patron[1:]):
                    return True
            elif patron == nombre:
                return True
        return False

    def encontrar_archivos(self):
        """Encuentra todos los archivos en el sistema"""
        archivos_encontrados = []
        
        for archivo in self.archivos_objetivo:
            ruta = self.directorio_base / archivo
            if ruta.exists():
                archivos_encontrados.append(ruta)
            else:
                print(f"⚠️  No encontrado: {archivo}")
        
        return sorted(archivos_encontrados)

    def leer_archivo_texto(self, ruta):
        """Lee un archivo de texto con manejo de codificación"""
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(ruta, 'r', encoding='latin-1') as f:
                    return f.read()
            except:
                return f"[ERROR: No se pudo leer el archivo {ruta.name}]"
        except Exception as e:
            return f"[ERROR: {str(e)}]"

    def leer_archivo_binario(self, ruta):
        """Lee un archivo binario y lo convierte a representación base64"""
        try:
            with open(ruta, 'rb') as f:
                contenido = f.read()
                # Intentar detectar si es texto
                try:
                    return contenido.decode('utf-8')
                except:
                    import base64
                    return f"[ARCHIVO BINARIO: {base64.b64encode(contenido[:100]).decode()}...]"
        except Exception as e:
            return f"[ERROR: {str(e)}]"

    def generar_arbol_directorios(self):
        """Genera un árbol de directorios del proyecto"""
        arbol = []
        
        def walk_dir(directorio, prefijo=""):
            try:
                items = sorted(directorio.iterdir())
                archivos = [item for item in items if item.is_file()]
                directorios = [item for item in items if item.is_dir()]
                
                # Filtrar archivos ignorados
                archivos = [a for a in archivos if not self.debe_ignorar(a)]
                directorios = [d for d in directorios if not self.debe_ignorar(d)]
                
                # Primero los directorios
                for i, d in enumerate(directorios):
                    es_ultimo = (i == len(directorios) - 1) and not archivos
                    simbolo = "└── " if es_ultimo else "├── "
                    arbol.append(f"{prefijo}{simbolo}{d.name}/")
                    
                    nuevo_prefijo = prefijo + ("    " if es_ultimo else "│   ")
                    walk_dir(d, nuevo_prefijo)
                
                # Luego los archivos
                for i, f in enumerate(archivos):
                    es_ultimo = (i == len(archivos) - 1)
                    simbolo = "└── " if es_ultimo else "├── "
                    arbol.append(f"{prefijo}{simbolo}{f.name}")
                    
            except PermissionError:
                arbol.append(f"{prefijo}└── [PERMISO DENEGADO]")
                
        arbol.append(f"{self.directorio_base.name}/")
        walk_dir(self.directorio_base, "")
        return "\n".join(arbol)

    def extraer_contenido(self):
        """Extrae todo el contenido del sistema"""
        print(f"🔍 Buscando archivos en: {self.directorio_base}")
        
        archivos = self.encontrar_archivos()
        
        if not archivos:
            print("❌ No se encontraron archivos")
            return None
        
        # Metadata
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        contenido = [
            "=" * 80,
            " EXTRACCIÓN COMPLETA DEL SISTEMA ASISTENTE IA",
            "=" * 80,
            f"Fecha de extracción: {timestamp}",
            f"Directorio base: {self.directorio_base}",
            f"Total de archivos: {len(archivos)}",
            "",
            "=" * 80,
            " ESTRUCTURA DE DIRECTORIOS",
            "=" * 80,
            "",
            self.generar_arbol_directorios(),
            "",
            "=" * 80,
            " CONTENIDO DE ARCHIVOS",
            "=" * 80,
            ""
        ]
        
        # Extraer cada archivo
        for ruta in archivos:
            try:
                rel_path = ruta.relative_to(self.directorio_base)
                extension = ruta.suffix.lower()
                
                contenido.append(f"\n{'-' * 60}")
                contenido.append(f"[FILE NAME]: {rel_path}")
                contenido.append(f"{'-' * 60}\n")
                
                # Determinar tipo de archivo
                if extension in ['.png', '.jpg', '.jpeg', '.gif', '.ico']:
                    contenido.append(self.leer_archivo_binario(ruta))
                else:
                    texto = self.leer_archivo_texto(ruta)
                    
                    # Para archivos JSON, formatear bonito
                    if extension == '.json':
                        try:
                            datos = json.loads(texto)
                            texto = json.dumps(datos, indent=2, ensure_ascii=False)
                        except:
                            pass
                    
                    contenido.append(texto)
                    
            except Exception as e:
                contenido.append(f"[ERROR procesando {ruta.name}: {str(e)}]")
        
        # Agregar resumen final
        contenido.extend([
            "",
            "=" * 80,
            " RESUMEN DE EXTRACCIÓN",
            "=" * 80,
            f"✅ Archivos extraídos: {len(archivos)}",
            f"📁 Directorio base: {self.directorio_base}",
            f"🕐 Fecha: {timestamp}",
            "=" * 80
        ])
        
        return "\n".join(contenido)

    def guardar_archivo(self, contenido, nombre_salida="output_completo.txt"):
        """Guarda el contenido en un archivo"""
        if not contenido:
            print("❌ No hay contenido para guardar")
            return False
        
        ruta_salida = self.directorio_base / nombre_salida
        
        try:
            with open(ruta_salida, 'w', encoding='utf-8') as f:
                f.write(contenido)
            
            tamaño = len(contenido) / 1024  # KB
            print(f"\n✅ Archivo guardado: {ruta_salida}")
            print(f"📊 Tamaño: {tamaño:.2f} KB")
            
            # Mostrar resumen
            archivos_totales = len(self.encontrar_archivos())
            print(f"📁 Archivos procesados: {archivos_totales}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando archivo: {e}")
            return False

def main():
    print("🚀 EXTRACTOR DEL SISTEMA ASISTENTE IA")
    print("=" * 50)
    
    # Obtener directorio actual
    directorio_actual = os.getcwd()
    
    # Crear extractor
    extractor = ExtractorSistema(directorio_actual)
    
    # Extraer contenido
    print("⏳ Extrayendo contenido...")
    contenido = extractor.extraer_contenido()
    
    if contenido:
        # Guardar archivo
        extractor.guardar_archivo(contenido)
        
        print("\n" + "=" * 50)
        print("✅ Proceso completado exitosamente")
        print("=" * 50)
    else:
        print("❌ Error en la extracción")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)
