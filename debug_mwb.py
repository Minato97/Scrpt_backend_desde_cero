#!/usr/bin/env python3
"""
Script de debug para identificar problemas en el parseo de archivos .mwb
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from laravel_generator import WorkbenchParser


def debug_mwb_file(mwb_file: str):
    """Parsea y muestra información detallada del archivo .mwb"""
    
    print("=" * 70)
    print("  DEBUG - Análisis Detallado de Archivo .mwb")
    print("=" * 70)
    print(f"\nArchivo: {mwb_file}\n")
    
    # Parsear con modo debug activado
    parser = WorkbenchParser(mwb_file, debug=True)
    
    if not parser.parse():
        print("\n❌ Error al parsear el archivo")
        return False
    
    print(f"\n{'=' * 70}")
    print(f"  RESUMEN")
    print(f"{'=' * 70}\n")
    print(f"Tablas encontradas: {len(parser.tables)}")
    print(f"Relaciones encontradas: {len(parser.relationships)}\n")
    
    # Mostrar detalles de cada tabla
    for table in parser.tables:
        print(f"\n{'─' * 70}")
        print(f"📊 TABLA: {table['name']}")
        print(f"{'─' * 70}")
        print(f"Columnas: {len(table['columns'])}")
        print(f"Soft Deletes: {'Sí' if table['has_soft_deletes'] else 'No'}")
        print(f"\nDetalle de columnas:\n")
        
        for col in table['columns']:
            # Mostrar información completa
            print(f"  • {col['name']}")
            print(f"    ├─ Tipo: {col['type']}")
            print(f"    ├─ Longitud: {col['length'] if col['length'] else 'N/A'}")
            print(f"    ├─ Precisión: {col['precision'] if col['precision'] else 'N/A'}")
            print(f"    ├─ Escala: {col['scale'] if col['scale'] else 'N/A'}")
            print(f"    ├─ NOT NULL: {'Sí' if col['not_null'] else 'No'}")
            print(f"    ├─ Auto Increment: {'Sí' if col['auto_increment'] else 'No'}")
            print(f"    ├─ Default: {col['default'] if col['default'] else 'N/A'}")
            print(f"    └─ Comentario: {col['comment'] if col['comment'] else 'N/A'}")
            print()
    
    # Mostrar relaciones
    if parser.relationships:
        print(f"\n{'─' * 70}")
        print(f"🔗 RELACIONES (FOREIGN KEYS)")
        print(f"{'─' * 70}\n")
        
        for rel in parser.relationships:
            source = rel['source_table']
            target = rel['target_table']
            source_cols = ', '.join(rel['source_columns'])
            target_cols = ', '.join(rel['target_columns'])
            
            print(f"  • {source}.{source_cols} → {target}.{target_cols}")
            print(f"    ├─ Nombre: {rel['name']}")
            print(f"    ├─ ON DELETE: {rel['on_delete']}")
            print(f"    └─ ON UPDATE: {rel['on_update']}")
            print()
    
    # Detectar problemas comunes
    print(f"\n{'─' * 70}")
    print(f"⚠️  PROBLEMAS DETECTADOS")
    print(f"{'─' * 70}\n")
    
    problems = []
    
    for table in parser.tables:
        for col in table['columns']:
            # Problema 1: Longitud inválida en strings
            if col['type'].lower() in ['varchar', 'char']:
                length = col['length']
                if not length or length == '' or length == '-1':
                    problems.append(f"❌ {table['name']}.{col['name']}: Longitud inválida '{length}' (se usará 255)")
                elif str(length).replace('-', '').isdigit() and int(length) < 0:
                    problems.append(f"❌ {table['name']}.{col['name']}: Longitud negativa {length} (se usará 255)")
            
            # Problema 2: Tipo desconocido
            valid_types = ['int', 'integer', 'tinyint', 'smallint', 'mediumint', 'bigint',
                          'varchar', 'char', 'text', 'mediumtext', 'longtext',
                          'decimal', 'float', 'double', 'boolean', 'bool',
                          'date', 'datetime', 'timestamp', 'time', 'year', 'json', 'enum']
            
            base_type = col['type'].lower().split('(')[0].strip()
            if base_type not in valid_types:
                problems.append(f"⚠️  {table['name']}.{col['name']}: Tipo '{col['type']}' no reconocido (se usará string)")
    
    # Problema 3: FK sin relación
    for table in parser.tables:
        for col in table['columns']:
            if col['name'].endswith('_id') and col['name'] != 'id':
                # Verificar si hay relación
                has_relation = False
                for rel in parser.relationships:
                    if rel['source_table'] == table['name'] and col['name'] in rel['source_columns']:
                        has_relation = True
                        break
                
                if not has_relation:
                    problems.append(f"⚠️  {table['name']}.{col['name']}: Parece FK pero no tiene relación definida")
    
    if problems:
        for problem in problems:
            print(f"  {problem}")
    else:
        print("  ✅ No se detectaron problemas")
    
    # Recomendaciones
    print(f"\n{'─' * 70}")
    print(f"💡 RECOMENDACIONES")
    print(f"{'─' * 70}\n")
    
    print("  1. Verifica que los tipos de datos estén correctamente definidos en Workbench")
    print("  2. Asegúrate de que las columnas VARCHAR tengan longitud especificada")
    print("  3. Define las foreign keys en el diagrama EER de Workbench")
    print("  4. Usa la convención tabla_singular_id para columnas FK (ej: user_id)")
    print("  5. Agrega created_at y updated_at para timestamps automáticos")
    print()
    
    return True


def main():
    if len(sys.argv) < 2:
        print("Uso: python debug_mwb.py <archivo.mwb>")
        sys.exit(1)
    
    mwb_file = sys.argv[1]
    
    if not os.path.exists(mwb_file):
        print(f"❌ Error: El archivo {mwb_file} no existe")
        sys.exit(1)
    
    try:
        debug_mwb_file(mwb_file)
    except Exception as e:
        print(f"\n❌ Error durante el análisis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
