#!/usr/bin/env python3
"""
Laravel Backend Generator from MySQL Workbench Models
Genera modelos, migraciones, controladores y rutas de Laravel desde archivos .mwb
"""
import shutil
import zipfile
import xml.etree.ElementTree as ET
import os
import sys
from typing import Dict, List, Tuple
import re
from datetime import datetime


class WorkbenchParser:
    """Parser para archivos .mwb de MySQL Workbench"""
    
    def __init__(self, mwb_file: str, debug: bool = False):
        self.mwb_file = mwb_file
        self.tables = []
        self.relationships = []
        self.debug = debug
        
    def parse(self):
        """Extrae y parsea el XML del archivo .mwb"""
        try:
            with zipfile.ZipFile(self.mwb_file, 'r') as zip_ref:
                # El archivo document.mwb.xml contiene el modelo
                with zip_ref.open('document.mwb.xml') as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    self._extract_tables(root)
                    self._extract_relationships(root)
            return True
        except Exception as e:
            print(f"Error al parsear el archivo .mwb: {e}")
            return False
    
    def _extract_tables(self, root):
        """Extrae información de las tablas"""
        # Buscar todas las tablas en el modelo
        for table in root.findall(".//value[@struct-name='db.mysql.Table']"):
            table_info = {
                'name': self._get_text(table, "value[@key='name']"),
                'comment': self._get_text(table, "value[@key='comment']"),
                'columns': [],
                'indexes': [],
                'has_soft_deletes': False
            }
            
            # Extraer columnas
            columns = table.find("value[@key='columns']")
            if columns is not None:
                for col in columns.findall("value"):
                    column_info = self._extract_column(col)
                    table_info['columns'].append(column_info)
                    
                    # Detectar si tiene soft deletes
                    if column_info['name'] == 'deleted_at':
                        table_info['has_soft_deletes'] = True
            
            # Extraer índices
            indices = table.find("value[@key='indices']")
            if indices is not None:
                for idx in indices.findall("value"):
                    index_info = self._extract_index(idx)
                    table_info['indexes'].append(index_info)
            
            self.tables.append(table_info)
    
    def _extract_column(self, column_elem):
        """Extrae información de una columna"""
        # Obtener el tipo de la columna
        simple_type = self._get_text(column_elem, "value[@key='simpleType']")
        user_type = self._get_text(column_elem, "link[@key='userType']")
        
        # Priorizar simpleType sobre userType
        col_type = simple_type if simple_type else user_type
        if not col_type:
            col_type = 'varchar'
        
        # Limpiar el tipo (remover cualquier cosa después del nombre)
        col_type = col_type.split('.')[-1] if '.' in col_type else col_type
        
        col_name = self._get_text(column_elem, "value[@key='name']")
        is_auto_inc = self._get_text(column_elem, "value[@key='autoIncrement']") == '1'
        
        # CORRECCIÓN INTELIGENTE DE TIPOS
        # Si es auto_increment y varchar, cambiar a BIGINT
        if is_auto_inc and col_type.lower() == 'varchar':
            col_type = 'BIGINT'
            if self.debug:
                print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a BIGINT (auto_increment)")
        
        # Si el nombre sugiere un tipo específico, corregir
        col_name_lower = col_name.lower()
        if col_type.lower() == 'varchar':
            # IDs deberían ser BIGINT
            if col_name_lower.endswith('_id') or col_name_lower == 'id':
                col_type = 'BIGINT'
                if self.debug:
                    print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a BIGINT (parece ID)")
            
            # Fechas deberían ser DATE o DATETIME
            elif 'fecha' in col_name_lower or 'date' in col_name_lower:
                if 'hora' in col_name_lower or 'time' in col_name_lower or 'creacion' in col_name_lower or 'reservacion' in col_name_lower:
                    col_type = 'DATETIME'
                    if self.debug:
                        print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a DATETIME")
                else:
                    col_type = 'DATE'
                    if self.debug:
                        print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a DATE")
            
            # Horas deberían ser TIME
            elif 'hora' in col_name_lower or 'time' in col_name_lower:
                col_type = 'TIME'
                if self.debug:
                    print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a TIME")
            
            # Edad, precio, costo deberían ser INT o DECIMAL
            elif col_name_lower in ['edad', 'age', 'years']:
                col_type = 'INT'
                if self.debug:
                    print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a INT")
            
            elif 'precio' in col_name_lower or 'costo' in col_name_lower or 'price' in col_name_lower or 'cost' in col_name_lower:
                col_type = 'DECIMAL'
                if self.debug:
                    print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a DECIMAL")
        
        col_info = {
            'name': col_name,
            'type': col_type,
            'length': self._get_text(column_elem, "value[@key='length']"),
            'precision': self._get_text(column_elem, "value[@key='precision']"),
            'scale': self._get_text(column_elem, "value[@key='scale']"),
            'not_null': self._get_text(column_elem, "value[@key='isNotNull']") == '1',
            'auto_increment': is_auto_inc,
            'default': self._get_text(column_elem, "value[@key='defaultValue']"),
            'comment': self._get_text(column_elem, "value[@key='comment']"),
        }
        
        if self.debug:
            print(f"  DEBUG Column: {col_info['name']} - Type: {col_info['type']} - Length: {col_info['length']}")
        
        return col_info
    
    def _extract_index(self, index_elem):
        """Extrae información de un índice"""
        idx_info = {
            'name': self._get_text(index_elem, "value[@key='name']"),
            'type': self._get_text(index_elem, "value[@key='indexType']"),
            'unique': self._get_text(index_elem, "value[@key='unique']") == '1',
            'columns': []
        }
        
        # Extraer columnas del índice
        columns = index_elem.find("value[@key='columns']")
        if columns is not None:
            for col_ref in columns.findall(".//link"):
                col_name = col_ref.text.split('/')[-1] if col_ref.text else ''
                if col_name:
                    idx_info['columns'].append(col_name)
        
        return idx_info
    
    def _extract_relationships(self, root):
        """Extrae relaciones entre tablas (foreign keys)"""
        # Primero crear un mapa de IDs a nombres de tablas y columnas
        table_map = {}
        column_map = {}
        
        # Mapear tablas
        for table in root.findall(".//value[@struct-name='db.mysql.Table']"):
            table_id = table.get('id')
            table_name = self._get_text(table, "value[@key='name']")
            if table_id and table_name:
                table_map[table_id] = table_name
            
            # Mapear columnas de esta tabla
            columns = table.find("value[@key='columns']")
            if columns is not None:
                for col in columns.findall("value"):
                    col_id = col.get('id')
                    col_name = self._get_text(col, "value[@key='name']")
                    if col_id and col_name:
                        column_map[col_id] = col_name
        
        # Ahora extraer foreign keys con nombres reales
        for fk in root.findall(".//value[@struct-name='db.mysql.ForeignKey']"):
            rel_info = {
                'name': self._get_text(fk, "value[@key='name']"),
                'source_table': None,
                'target_table': None,
                'source_columns': [],
                'target_columns': [],
                'on_delete': self._get_text(fk, "value[@key='deleteRule']", 'RESTRICT'),
                'on_update': self._get_text(fk, "value[@key='updateRule']", 'RESTRICT'),
            }
            
            # Obtener tabla origen
            owner_link = fk.find("link[@key='owner']")
            if owner_link is not None and owner_link.text:
                owner_id = owner_link.text
                rel_info['source_table'] = table_map.get(owner_id, owner_id)
            
            # Obtener tabla destino
            ref_table_link = fk.find("link[@key='referencedTable']")
            if ref_table_link is not None and ref_table_link.text:
                ref_id = ref_table_link.text
                rel_info['target_table'] = table_map.get(ref_id, ref_id)
            
            # Obtener columnas origen
            columns = fk.find("value[@key='columns']")
            if columns is not None:
                for col_link in columns.findall(".//link"):
                    if col_link.text:
                        col_id = col_link.text
                        col_name = column_map.get(col_id, col_id)
                        rel_info['source_columns'].append(col_name)
            
            # Obtener columnas destino
            ref_columns = fk.find("value[@key='referencedColumns']")
            if ref_columns is not None:
                for col_link in ref_columns.findall(".//link"):
                    if col_link.text:
                        col_id = col_link.text
                        col_name = column_map.get(col_id, col_id)
                        rel_info['target_columns'].append(col_name)
            
            if self.debug:
                print(f"  DEBUG Relation: {rel_info['source_table']}.{rel_info['source_columns']} → {rel_info['target_table']}.{rel_info['target_columns']}")
            
            self.relationships.append(rel_info)
    
    def _get_text(self, element, path, default=''):
        """Helper para obtener texto de un elemento XML"""
        found = element.find(path)
        return found.text if found is not None and found.text else default


class LaravelGenerator:
    """Generador de código Laravel"""
    
    def __init__(self, tables: List[Dict], relationships: List[Dict], output_dir: str):
        self.tables = tables
        self.relationships = relationships
        self.output_dir = output_dir
        self.migration_counter = 1

    def _sort_tables_by_dependencies(self):
        """
        Ordena las tablas según dependencias de foreign keys.
        Tablas sin dependencias primero.
        """
        dependency_map = {table['name']: set() for table in self.tables}

        # Construir mapa de dependencias
        for rel in self.relationships:
            source = rel['source_table']
            target = rel['target_table']

            if source and target:
                dependency_map[source].add(target)

        sorted_tables = []
        visited = set()

        def visit(table_name):
            if table_name in visited:
                return
            visited.add(table_name)

            for dep in dependency_map[table_name]:
                visit(dep)

            sorted_tables.append(table_name)

        for table in dependency_map:
            visit(table)

        # Reordenar self.tables
        ordered = []
        for name in sorted_tables:
            for table in self.tables:
                if table['name'] == name:
                    ordered.append(table)

        self.tables = ordered

    def generate_all(self):
        """Genera todos los archivos de Laravel"""
        self._create_directories()
        self._sort_tables_by_dependencies()

        for table in self.tables:
            print(f"Generando archivos para tabla: {table['name']}")

            # Siempre generar migración
            self.generate_migration(table)

            # No generar modelo para la tabla users
            if table['name'].lower() != 'users':
                self.generate_model(table)
            else:
                print("  ⚠️  Modelo omitido para tabla 'users'")

            # Siempre generar controlador
            self.generate_controller(table)
        
        self.generate_routes()
        print(f"\n✓ Generación completada en: {self.output_dir}")
        print("\nPróximos pasos:")
        print("1. Copia las migraciones a database/migrations/")
        print("2. Copia los modelos a app/Models/")
        print("3. Copia los controladores a app/Http/Controllers/Api/")
        print("4. Agrega las rutas de api.php a tu proyecto")
        print("5. Ejecuta: php artisan migrate")

    def _create_directories(self):
        """Crea estructura limpia de directorios (borra contenido previo)"""
        dirs = [
            f"{self.output_dir}/migrations",
            f"{self.output_dir}/models",
            f"{self.output_dir}/controllers",
            f"{self.output_dir}/routes"
        ]

        for dir_path in dirs:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)  # 🔥 BORRA TODO EL DIRECTORIO
            os.makedirs(dir_path)
    
    def generate_migration(self, table: Dict):
        """Genera archivo de migración"""
        table_name = table['name']
        class_name = self._to_studly_case(f"create_{table_name}_table")
        
        # Timestamp para el nombre del archivo
        timestamp = datetime.now().strftime('%Y_%m_%d_%H%M%S')
        timestamp = f"{timestamp}_{self.migration_counter:02d}"
        migration_number = str(self.migration_counter).zfill(2)
        filename = f"{timestamp}_{migration_number}_create_{table_name}_table.php"
        
        # Generar contenido
        content = self._generate_migration_content(table, class_name)
        
        # Guardar archivo
        filepath = f"{self.output_dir}/migrations/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.migration_counter += 1
    
    def _generate_migration_content(self, table: Dict, class_name: str) -> str:
        """Genera el contenido de la migración"""
        table_name = table['name']
        columns_code = []
        
        # Pasar table_name a _column_to_migration
        for col in table['columns']:
            col_line = self._column_to_migration(col, table_name)
            if col_line:
                columns_code.append(f"            {col_line}")
        
        # Agregar foreign keys
        fk_code = []
        for rel in self.relationships:
            if rel['source_table'] == table_name:
                fk_line = self._relationship_to_migration(rel)
                if fk_line:
                    fk_code.append(f"            {fk_line}")
        
        # Agregar timestamps y softDeletes al final si aplica
        has_timestamps = any(col['name'] in ['created_at', 'updated_at'] for col in table['columns'])
        has_soft_deletes = table['has_soft_deletes']
        
        special_columns = []
        # Agregar timestamps a TODAS las tablas por defecto
        special_columns.append("            $table->timestamps();")
        
        if has_soft_deletes:
            special_columns.append("            $table->softDeletes();")
        
        columns_str = "\n".join(columns_code)
        fk_str = "\n" + "\n".join(fk_code) if fk_code else ""
        special_str = "\n\n" + "\n".join(special_columns) if special_columns else ""
        
        return f"""<?php

use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{{
    /**
     * Run the migrations.
     */
    public function up(): void
    {{
        Schema::create('{table_name}', function (Blueprint $table) {{
{columns_str}{fk_str}{special_str}
        }});
    }}

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {{
        Schema::dropIfExists('{table_name}');
    }}
}};
"""
    
    def _column_to_migration(self, col: Dict, table_name: str = None) -> str:
        """Convierte una columna a código de migración Laravel"""
        name = col['name']
        col_type = col['type'].lower().strip()
        
        # Verificar si esta columna es una foreign key
        is_fk = self._is_foreign_key_column(name, table_name)
        if is_fk:
            # No generar la columna aquí, será manejada por foreignId()->constrained()
            return None
        
        # Limpiar el tipo (remover paréntesis y argumentos)
        base_type = col_type.split('(')[0].strip()
        
        # Mapeo de tipos MySQL a Laravel
        type_map = {
            'int': 'integer',
            'integer': 'integer',
            'tinyint': 'tinyInteger',
            'smallint': 'smallInteger',
            'mediumint': 'mediumInteger',
            'bigint': 'bigInteger',
            'varchar': 'string',
            'char': 'char',
            'text': 'text',
            'mediumtext': 'mediumText',
            'longtext': 'longText',
            'decimal': 'decimal',
            'float': 'float',
            'double': 'double',
            'boolean': 'boolean',
            'bool': 'boolean',
            'date': 'date',
            'datetime': 'dateTime',
            'timestamp': 'timestamp',
            'time': 'time',
            'year': 'year',
            'json': 'json',
            'enum': 'enum',
            'blob': 'binary',
            'binary': 'binary',
        }
        
        laravel_type = type_map.get(base_type, 'string')
        
        # Casos especiales
        if name == 'id':
            # Para columnas llamadas id, usar $table->id() si es bigint/int
            if base_type in ['bigint', 'int', 'integer']:
                return "$table->id();"
            else:
                # Si es otro tipo (raro), crear como string
                return "$table->string('id');"
        
        if name in ['created_at', 'updated_at']:
            return None  # Laravel los maneja con timestamps()
        
        if name == 'deleted_at':
            return None  # Se maneja con softDeletes()
        
        # Construir la definición
        if laravel_type in ['string', 'char']:
            # Validar longitud
            length = col['length']
            if not length or length == '' or length == '-1' or not str(length).replace('-','').isdigit():
                length = '255'
            elif int(length) < 0:
                length = '255'
            line = f"$table->{laravel_type}('{name}', {length})"
        elif laravel_type == 'decimal':
            precision = col['precision'] if col['precision'] and str(col['precision']).isdigit() else '8'
            scale = col['scale'] if col['scale'] and str(col['scale']).isdigit() else '2'
            line = f"$table->decimal('{name}', {precision}, {scale})"
        elif laravel_type in ['integer', 'bigInteger', 'tinyInteger', 'smallInteger', 'mediumInteger']:
            line = f"$table->{laravel_type}('{name}')"
            if col['auto_increment']:
                line += "->autoIncrement()"
        else:
            line = f"$table->{laravel_type}('{name}')"
        
        # Modificadores
        if not col['not_null'] and name != 'id':
            line += "->nullable()"
        
        if col['default'] and col['default'] not in ['NULL', 'null', '']:
            default_val = col['default']
            # Si es string, agregar comillas
            if laravel_type in ['string', 'char', 'text', 'mediumText', 'longText']:
                line += f"->default('{default_val}')"
            else:
                line += f"->default({default_val})"
        
        # Índices especiales
        if 'email' in name.lower() and laravel_type == 'string':
            line += "->unique()"
        
        if col['comment']:
            comment = col['comment'].replace("'", "\\'")
            line += f"->comment('{comment}')"
        
        line += ";"
        return line
    
    def _is_foreign_key_column(self, column_name: str, table_name: str = None) -> bool:
        """Verifica si una columna es foreign key"""
        # Primero verificar en las relaciones explícitas
        for rel in self.relationships:
            if column_name in rel.get('source_columns', []):
                if table_name is None or rel.get('source_table') == table_name:
                    return True
        
        # Si no está en relaciones pero termina en _id (excepto 'id'), es FK potencial
        if column_name.endswith('_id') and column_name != 'id':
            return True
        
        return False
    
    def _relationship_to_migration(self, rel: Dict) -> str:
        """Convierte una relación a foreign key en migración usando foreignId()->constrained()"""
        if not rel['source_columns'] or not rel['target_columns']:
            return ""
        
        source_col = rel['source_columns'][0]
        target_table = rel['target_table']
        
        # Determinar si la columna es nullable
        is_nullable = False
        for table in self.tables:
            if table['name'] == rel['source_table']:
                for col in table['columns']:
                    if col['name'] == source_col and not col['not_null']:
                        is_nullable = True
                        break
        
        # Construir la línea usando foreignId()->constrained()
        nullable_str = "->nullable()" if is_nullable else ""
        line = f"$table->foreignId('{source_col}'){nullable_str}"
        line += f"->constrained('{target_table}')"
        
        # On delete/update usando métodos modernos de Laravel
        on_delete = rel['on_delete'].lower()
        on_update = rel['on_update'].lower()
        
        if on_delete == 'cascade':
            line += "->cascadeOnDelete()"
        elif on_delete == 'set null':
            line += "->nullOnDelete()"
        elif on_delete == 'restrict':
            line += "->restrictOnDelete()"
        
        if on_update == 'cascade':
            line += "->cascadeOnUpdate()"
        elif on_update == 'restrict':
            line += "->restrictOnUpdate()"
        
        line += ";"
        return line
    
    def generate_model(self, table: Dict):
        """Genera el modelo Eloquent"""
        table_name = table['name']
        model_name = self._to_studly_case(self._singular(table_name))
        
        content = self._generate_model_content(table, model_name)
        
        filepath = f"{self.output_dir}/models/{model_name}.php"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_model_content(self, table: Dict, model_name: str) -> str:
        """Genera el contenido del modelo"""
        table_name = table['name']
        
        # Fillable columns (excluir id, timestamps, etc.)
        fillable = []
        for col in table['columns']:
            if col['name'] not in ['id', 'created_at', 'updated_at', 'deleted_at']:
                fillable.append(f"'{col['name']}'")
        
        fillable_str = ",\n        ".join(fillable)
        
        # Casts
        casts = []
        for col in table['columns']:
            col_type = col['type'].lower()
            name = col['name']
            
            if col_type in ['datetime', 'timestamp']:
                casts.append(f"'{name}' => 'datetime'")
            elif col_type == 'date':
                casts.append(f"'{name}' => 'date'")
            elif col_type == 'json':
                casts.append(f"'{name}' => 'array'")
            elif col_type == 'boolean':
                casts.append(f"'{name}' => 'boolean'")
            elif col_type in ['int', 'tinyint', 'smallint', 'mediumint', 'bigint']:
                casts.append(f"'{name}' => 'integer'")
            elif col_type in ['decimal', 'float', 'double']:
                casts.append(f"'{name}' => 'float'")
        
        casts_str = ",\n        ".join(casts) if casts else ""
        
        # Relaciones
        relationships_code = self._generate_relationships(table_name, model_name)
        
        # Traits
        traits = ["use HasFactory;"]
        if table['has_soft_deletes']:
            traits.append("use SoftDeletes;")
        
        traits_str = "\n    ".join(traits)
        
        use_statements = ["use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;",
                         "use Illuminate\\Database\\Eloquent\\Model;"]
        
        if table['has_soft_deletes']:
            use_statements.append("use Illuminate\\Database\\Eloquent\\SoftDeletes;")
        
        use_str = "\n".join(use_statements)
        
        return f"""<?php

namespace App\\Models;

{use_str}

class {model_name} extends Model
{{
    {traits_str}

    protected $table = '{table_name}';

    protected $fillable = [
        {fillable_str}
    ];

    protected $casts = [
        {casts_str}
    ];
{relationships_code}
}}
"""
    
    def _generate_relationships(self, table_name: str, model_name: str) -> str:
        """Genera métodos de relaciones del modelo"""
        relationships = []
        
        # belongsTo (esta tabla tiene FK hacia otras)
        for rel in self.relationships:
            if rel['source_table'] == table_name:
                target_model = self._to_studly_case(self._singular(rel['target_table']))
                source_col = rel['source_columns'][0] if rel['source_columns'] else 'id'
                method_name = self._to_camel_case(self._singular(rel['target_table']))
                
                relationships.append(f"""
    public function {method_name}()
    {{
        return $this->belongsTo({target_model}::class, '{source_col}');
    }}""")
        
        # hasMany (otras tablas tienen FK hacia esta)
        for rel in self.relationships:
            if rel['target_table'] == table_name:
                source_model = self._to_studly_case(self._singular(rel['source_table']))
                foreign_col = rel['source_columns'][0] if rel['source_columns'] else 'id'
                method_name = self._to_camel_case(rel['source_table'])  # plural
                
                relationships.append(f"""
    public function {method_name}()
    {{
        return $this->hasMany({source_model}::class, '{foreign_col}');
    }}""")
        
        return "".join(relationships)
    
    def generate_controller(self, table: Dict):
        """Genera el controlador API"""
        table_name = table['name']
        model_name = self._to_studly_case(self._singular(table_name))
        controller_name = f"{model_name}Controller"
        
        content = self._generate_controller_content(table, model_name, controller_name)
        
        filepath = f"{self.output_dir}/controllers/{controller_name}.php"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_controller_content(self, table: Dict, model_name: str, controller_name: str) -> str:
        """Genera el contenido del controlador"""
        
        # Generar reglas de validación
        validation_rules = self._generate_validation_rules(table)
        
        # Variable en minúsculas para instancia
        var_name = self._to_camel_case(model_name)
        
        # Obtener relaciones para eager loading
        with_relations = self._get_with_relations(table['name'])
        load_relations = self._get_load_relations_string(table['name'])
        
        return f"""<?php

namespace App\\Http\\Controllers\\Api;

use App\\Http\\Controllers\\Controller;
use App\\Models\\{model_name};
use Illuminate\\Http\\Request;
use Illuminate\\Http\\JsonResponse;

class {controller_name} extends Controller
{{
    /**
     * Display a listing of the resource.
     */
    public function index(): JsonResponse
    {{
        ${var_name}s = {model_name}::query(){with_relations}->get();
        
        return response()->json([
            'success' => true,
            'data' => ${var_name}s
        ]);
    }}

    /**
     * Store a newly created resource in storage.
     */
    public function store(Request $request): JsonResponse
    {{
        $validated = $request->validate([
{validation_rules}
        ]);

        ${var_name} = {model_name}::create($validated);
        
        // Cargar relaciones
        {load_relations}

        return response()->json([
            'success' => true,
            'message' => '{model_name} created successfully',
            'data' => ${var_name}
        ], 201);
    }}

    /**
     * Display the specified resource.
     */
    public function show({model_name} ${var_name}): JsonResponse
    {{
        // Cargar relaciones
        {load_relations}
        
        return response()->json([
            'success' => true,
            'data' => ${var_name}
        ]);
    }}

    /**
     * Update the specified resource in storage.
     */
    public function update(Request $request, {model_name} ${var_name}): JsonResponse
    {{
        $validated = $request->validate([
{validation_rules}
        ]);

        ${var_name}->update($validated);
        
        // Recargar relaciones
        {load_relations}

        return response()->json([
            'success' => true,
            'message' => '{model_name} updated successfully',
            'data' => ${var_name}
        ]);
    }}

    /**
     * Remove the specified resource from storage.
     */
    public function destroy({model_name} ${var_name}): JsonResponse
    {{
        ${var_name}->delete();

        return response()->json([
            'success' => true,
            'message' => '{model_name} deleted successfully'
        ]);
    }}
}}
"""
    
    def _get_with_relations(self, table_name: str) -> str:
        """Obtiene las relaciones para usar con ->with() en queries"""
        relations = []
        
        # belongsTo (esta tabla tiene FK hacia otras)
        for rel in self.relationships:
            if rel['source_table'] == table_name:
                method_name = self._to_camel_case(self._singular(rel['target_table']))
                relations.append(f"'{method_name}'")
        
        if relations:
            return f"->with([{', '.join(relations)}])"
        return ""
    
    def _get_load_relations_string(self, table_name: str) -> str:
        """Obtiene string para cargar relaciones con ->load()"""
        relations = []
        
        # belongsTo (esta tabla tiene FK hacia otras)
        for rel in self.relationships:
            if rel['source_table'] == table_name:
                method_name = self._to_camel_case(self._singular(rel['target_table']))
                relations.append(f"'{method_name}'")
        
        if relations:
            var_name = self._to_camel_case(self._singular(table_name))
            return f"${var_name}->load([{', '.join(relations)}]);"
        return "// No hay relaciones para cargar"
    
    def _generate_validation_rules(self, table: Dict) -> str:
        """Genera reglas de validación para el controlador"""
        rules = []
        
        for col in table['columns']:
            if col['name'] in ['id', 'created_at', 'updated_at', 'deleted_at']:
                continue
            
            rule_parts = []
            
            # Required si not null
            if col['not_null']:
                rule_parts.append('required')
            else:
                rule_parts.append('nullable')
            
            # Tipo
            col_type = col['type'].lower()
            if col_type in ['int', 'tinyint', 'smallint', 'mediumint', 'bigint']:
                rule_parts.append('integer')
            elif col_type in ['decimal', 'float', 'double']:
                rule_parts.append('numeric')
            elif col_type in ['varchar', 'char', 'text', 'mediumtext', 'longtext']:
                rule_parts.append('string')
                if col['length']:
                    rule_parts.append(f'max:{col["length"]}')
            elif col_type in ['date']:
                rule_parts.append('date')
            elif col_type in ['datetime', 'timestamp']:
                rule_parts.append('date')
            elif col_type == 'boolean':
                rule_parts.append('boolean')
            elif col_type == 'json':
                rule_parts.append('array')
            
            # Foreign keys
            is_foreign_key = False
            for rel in self.relationships:
                if rel['source_table'] == table['name'] and col['name'] in rel['source_columns']:
                    target_table = rel['target_table']
                    target_col = rel['target_columns'][0] if rel['target_columns'] else 'id'
                    rule_parts.append(f'exists:{target_table},{target_col}')
                    is_foreign_key = True
                    break
            
            rule_str = '|'.join(rule_parts)
            rules.append(f"            '{col['name']}' => '{rule_str}'")
        
        return ",\n".join(rules)

    def generate_routes(self):
        """Genera el archivo de rutas API"""

        routes = []

        for table in self.tables:
            model_name = self._to_studly_case(self._singular(table['name']))
            controller_name = f"{model_name}Controller"
            route_name = self._to_kebab_case(table['name'])


            # Agregar ruta
            routes.append(
                f"Route::apiResource('{route_name}', "
                f"\\App\\Http\\Controllers\\Api\\{controller_name}::class);"
            )

        routes_str = "\n".join(routes)

        content = f"""<?php

    use Illuminate\\Http\\Request;
    use Illuminate\\Support\\Facades\\Route;
 

    /*
    |--------------------------------------------------------------------------
    | API Routes
    |--------------------------------------------------------------------------
    */

    // Rutas API generadas automáticamente
    {routes_str}
    """

        filepath = f"{self.output_dir}/routes/api.php"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    # Helper methods para conversión de nombres
    
    def _to_studly_case(self, string: str) -> str:
        """Convierte a StudlyCase (PascalCase)"""
        return ''.join(word.capitalize() for word in string.replace('_', ' ').split())
    
    def _to_camel_case(self, string: str) -> str:
        """Convierte a camelCase"""
        studly = self._to_studly_case(string)
        return studly[0].lower() + studly[1:] if studly else ''
    
    def _to_kebab_case(self, string: str) -> str:
        """Convierte a kebab-case"""
        return string.replace('_', '-').lower()
    
    def _singular(self, word: str) -> str:
        """Intenta singularizar una palabra (incluye español)"""
        word_lower = word.lower()
        
        # Palabras irregulares en español
        irregulars_es = {
            'clientes': 'cliente',
            'medicos': 'medico',
            'servicios': 'servicio',
            'horarios': 'horario',
            'estatus': 'estatus',  # Ya es singular
            'roles': 'rol',
            'users': 'user',
        }
        
        if word_lower in irregulars_es:
            # Mantener la capitalización original
            result = irregulars_es[word_lower]
            if word[0].isupper():
                result = result.capitalize()
            return result
        
        # Reglas en inglés
        if word.endswith('ies'):
            return word[:-3] + 'y'
        elif word.endswith('es'):
            return word[:-2]
        elif word.endswith('s'):
            return word[:-1]
        
        return word



def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print("Uso: python laravel_generator.py <archivo.mwb> [directorio_salida]")
        sys.exit(1)
    
    mwb_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'laravel_generated'
    
    if not os.path.exists(mwb_file):
        print(f"Error: El archivo {mwb_file} no existe")
        sys.exit(1)
    
    print("=" * 60)
    print("Laravel Backend Generator from MySQL Workbench")
    print("=" * 60)
    print(f"\nArchivo de entrada: {mwb_file}")
    print(f"Directorio de salida: {output_dir}\n")
    
    # Parsear el archivo .mwb
    print("Parseando archivo .mwb...")
    parser = WorkbenchParser(mwb_file)
    if not parser.parse():
        print("Error al parsear el archivo")
        sys.exit(1)
    
    print(f"✓ Se encontraron {len(parser.tables)} tablas")
    print(f"✓ Se encontraron {len(parser.relationships)} relaciones\n")
    
    # Generar archivos Laravel
    print("Generando archivos Laravel...")
    generator = LaravelGenerator(parser.tables, parser.relationships, output_dir)
    generator.generate_all()


if __name__ == '__main__':
    main()
