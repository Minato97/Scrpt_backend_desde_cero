#!/usr/bin/env python3
"""
Laravel Backend Generator from MySQL Workbench Models
Genera modelos, migraciones, controladores, seeders y rutas de Laravel desde archivos .mwb
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
        for table in root.findall(".//value[@struct-name='db.mysql.Table']"):
            table_info = {
                'name': self._get_text(table, "value[@key='name']"),
                'comment': self._get_text(table, "value[@key='comment']"),
                'columns': [],
                'indexes': [],
                'has_soft_deletes': False
            }

            columns = table.find("value[@key='columns']")
            if columns is not None:
                for col in columns.findall("value"):
                    column_info = self._extract_column(col)
                    table_info['columns'].append(column_info)

                    if column_info['name'] == 'deleted_at':
                        table_info['has_soft_deletes'] = True

            indices = table.find("value[@key='indices']")
            if indices is not None:
                for idx in indices.findall("value"):
                    index_info = self._extract_index(idx)
                    table_info['indexes'].append(index_info)

            self.tables.append(table_info)

    def _extract_column(self, column_elem):
        """Extrae información de una columna"""
        simple_type = self._get_text(column_elem, "value[@key='simpleType']")
        user_type = self._get_text(column_elem, "link[@key='userType']")

        col_type = simple_type if simple_type else user_type
        if not col_type:
            col_type = 'varchar'

        col_type = col_type.split('.')[-1] if '.' in col_type else col_type

        col_name = self._get_text(column_elem, "value[@key='name']")
        is_auto_inc = self._get_text(column_elem, "value[@key='autoIncrement']") == '1'

        if is_auto_inc and col_type.lower() == 'varchar':
            col_type = 'BIGINT'
            if self.debug:
                print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a BIGINT (auto_increment)")

        col_name_lower = col_name.lower()
        if col_type.lower() == 'varchar':
            if col_name_lower.endswith('_id') or col_name_lower == 'id':
                col_type = 'BIGINT'
                if self.debug:
                    print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a BIGINT (parece ID)")

            elif 'fecha' in col_name_lower or 'date' in col_name_lower:
                if 'hora' in col_name_lower or 'time' in col_name_lower or 'creacion' in col_name_lower or 'reservacion' in col_name_lower:
                    col_type = 'DATETIME'
                    if self.debug:
                        print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a DATETIME")
                else:
                    col_type = 'DATE'
                    if self.debug:
                        print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a DATE")

            elif 'hora' in col_name_lower or 'time' in col_name_lower:
                col_type = 'TIME'
                if self.debug:
                    print(f"  ⚠️  CORRECCIÓN: {col_name} cambiado de VARCHAR a TIME")

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

        columns = index_elem.find("value[@key='columns']")
        if columns is not None:
            for col_ref in columns.findall(".//link"):
                col_name = col_ref.text.split('/')[-1] if col_ref.text else ''
                if col_name:
                    idx_info['columns'].append(col_name)

        return idx_info

    def _extract_relationships(self, root):
        """Extrae relaciones entre tablas (foreign keys)"""
        table_map = {}
        column_map = {}

        for table in root.findall(".//value[@struct-name='db.mysql.Table']"):
            table_id = table.get('id')
            table_name = self._get_text(table, "value[@key='name']")
            if table_id and table_name:
                table_map[table_id] = table_name

            columns = table.find("value[@key='columns']")
            if columns is not None:
                for col in columns.findall("value"):
                    col_id = col.get('id')
                    col_name = self._get_text(col, "value[@key='name']")
                    if col_id and col_name:
                        column_map[col_id] = col_name

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

            owner_link = fk.find("link[@key='owner']")
            if owner_link is not None and owner_link.text:
                owner_id = owner_link.text
                rel_info['source_table'] = table_map.get(owner_id, owner_id)

            ref_table_link = fk.find("link[@key='referencedTable']")
            if ref_table_link is not None and ref_table_link.text:
                ref_id = ref_table_link.text
                rel_info['target_table'] = table_map.get(ref_id, ref_id)

            columns = fk.find("value[@key='columns']")
            if columns is not None:
                for col_link in columns.findall(".//link"):
                    if col_link.text:
                        col_id = col_link.text
                        col_name = column_map.get(col_id, col_id)
                        rel_info['source_columns'].append(col_name)

            ref_columns = fk.find("value[@key='referencedColumns']")
            if ref_columns is not None:
                for col_link in ref_columns.findall(".//link"):
                    if col_link.text:
                        col_id = col_link.text
                        col_name = column_map.get(col_id, col_id)
                        rel_info['target_columns'].append(col_name)

            if self.debug:
                print(
                    f"  DEBUG Relation: {rel_info['source_table']}.{rel_info['source_columns']} → {rel_info['target_table']}.{rel_info['target_columns']}")

            self.relationships.append(rel_info)

    def _get_text(self, element, path, default=''):
        """Helper para obtener texto de un elemento XML"""
        found = element.find(path)
        return found.text if found is not None and found.text else default


class LaravelGenerator:
    """Generador de código Laravel"""

    # Tablas excluidas de generación de seeders
    SEEDER_EXCLUDED_TABLES = {'users', 'rol', 'estatus', 'roles', 'status'}

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

            self.generate_migration(table)

            if table['name'].lower() != 'users':
                self.generate_model(table)
            else:
                print("  ⚠️  Modelo omitido para tabla 'users'")

            self.generate_controller(table)

            # Generar seeder solo para tablas no excluidas
            if table['name'].lower() not in self.SEEDER_EXCLUDED_TABLES:
                self.generate_seeder(table)
            else:
                print(f"  ⚠️  Seeder omitido para tabla '{table['name']}'")

        self.generate_routes()
        self.generate_database_seeder()

        print(f"\n✓ Generación completada en: {self.output_dir}")
        print("\nPróximos pasos:")
        print("1. Copia las migraciones a database/migrations/")
        print("2. Copia los modelos a app/Models/")
        print("3. Copia los controladores a app/Http/Controllers/Api/")
        print("4. Copia los seeders a database/seeders/")
        print("5. Reemplaza database/seeders/DatabaseSeeder.php con el generado")
        print("6. Agrega las rutas de api.php a tu proyecto")
        print("7. Ejecuta: php artisan migrate --seed")

    def _create_directories(self):
        """Crea estructura limpia de directorios (borra contenido previo)"""
        dirs = [
            f"{self.output_dir}/migrations",
            f"{self.output_dir}/models",
            f"{self.output_dir}/controllers",
            f"{self.output_dir}/routes",
            f"{self.output_dir}/seeders",
        ]

        for dir_path in dirs:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
            os.makedirs(dir_path)

    def generate_migration(self, table: Dict):
        """Genera archivo de migración"""
        table_name = table['name']
        class_name = self._to_studly_case(f"create_{table_name}_table")

        timestamp = datetime.now().strftime('%Y_%m_%d_%H%M%S')
        timestamp = f"{timestamp}_{self.migration_counter:02d}"
        migration_number = str(self.migration_counter).zfill(2)
        filename = f"{timestamp}_{migration_number}_create_{table_name}_table.php"

        content = self._generate_migration_content(table, class_name)

        filepath = f"{self.output_dir}/migrations/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        self.migration_counter += 1

    def _generate_migration_content(self, table: Dict, class_name: str) -> str:
        """Genera el contenido de la migración"""
        table_name = table['name']
        columns_code = []

        for col in table['columns']:
            col_line = self._column_to_migration(col, table_name)
            if col_line:
                columns_code.append(f"            {col_line}")

        fk_code = []
        for rel in self.relationships:
            if rel['source_table'] == table_name:
                fk_line = self._relationship_to_migration(rel)
                if fk_line:
                    fk_code.append(f"            {fk_line}")

        has_soft_deletes = table['has_soft_deletes']

        special_columns = []
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

        is_fk = self._is_foreign_key_column(name, table_name)
        if is_fk:
            return None

        base_type = col_type.split('(')[0].strip()

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

        if name == 'id':
            if base_type in ['bigint', 'int', 'integer']:
                return "$table->id();"
            else:
                return "$table->string('id');"

        if name in ['created_at', 'updated_at']:
            return None

        if name == 'deleted_at':
            return None

        if laravel_type in ['string', 'char']:
            length = col['length']
            if not length or length == '' or length == '-1' or not str(length).replace('-', '').isdigit():
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

        if not col['not_null'] and name != 'id':
            line += "->nullable()"

        if col['default'] and col['default'] not in ['NULL', 'null', '']:
            default_val = col['default']
            if laravel_type in ['string', 'char', 'text', 'mediumText', 'longText']:
                line += f"->default('{default_val}')"
            else:
                line += f"->default({default_val})"

        if 'email' in name.lower() and laravel_type == 'string':
            line += "->unique()"

        if col['comment']:
            comment = col['comment'].replace("'", "\\'")
            line += f"->comment('{comment}')"

        line += ";"
        return line

    def _is_foreign_key_column(self, column_name: str, table_name: str = None) -> bool:
        """Verifica si una columna es foreign key"""
        for rel in self.relationships:
            if column_name in rel.get('source_columns', []):
                if table_name is None or rel.get('source_table') == table_name:
                    return True

        if column_name.endswith('_id') and column_name != 'id':
            return True

        return False

    def _relationship_to_migration(self, rel: Dict) -> str:
        """Convierte una relación a foreign key en migración usando foreignId()->constrained()"""
        if not rel['source_columns'] or not rel['target_columns']:
            return ""

        source_col = rel['source_columns'][0]
        target_table = rel['target_table']

        is_nullable = False
        for table in self.tables:
            if table['name'] == rel['source_table']:
                for col in table['columns']:
                    if col['name'] == source_col and not col['not_null']:
                        is_nullable = True
                        break

        nullable_str = "->nullable()" if is_nullable else ""
        line = f"$table->foreignId('{source_col}'){nullable_str}"
        line += f"->constrained('{target_table}')"

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

        fillable = []
        for col in table['columns']:
            if col['name'] not in ['id', 'created_at', 'updated_at', 'deleted_at']:
                fillable.append(f"'{col['name']}'")

        fillable_str = ",\n        ".join(fillable)

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

        relationships_code = self._generate_relationships(table_name, model_name)

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

        for rel in self.relationships:
            if rel['target_table'] == table_name:
                source_model = self._to_studly_case(self._singular(rel['source_table']))
                foreign_col = rel['source_columns'][0] if rel['source_columns'] else 'id'
                method_name = self._to_camel_case(rel['source_table'])

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
        validation_rules = self._generate_validation_rules(table)
        var_name = self._to_camel_case(model_name)
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

            if col['not_null']:
                rule_parts.append('required')
            else:
                rule_parts.append('nullable')

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

    # -------------------------------------------------------------------------
    # SEEDER GENERATION
    # -------------------------------------------------------------------------

    def generate_seeder(self, table: Dict):
        """Genera un seeder para la tabla usando Faker con 10 registros"""
        table_name = table['name']
        model_name = self._to_studly_case(self._singular(table_name))
        seeder_name = f"{model_name}Seeder"

        content = self._generate_seeder_content(table, model_name, seeder_name)

        filepath = f"{self.output_dir}/seeders/{seeder_name}.php"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✓ Seeder generado: {seeder_name}.php")

    def _generate_seeder_content(self, table: Dict, model_name: str, seeder_name: str) -> str:
        """Genera el contenido de un seeder con Faker"""
        table_name = table['name']

        # Construir el array de faker para cada columna
        faker_fields = self._build_faker_fields(table)
        faker_fields_str = "\n".join(faker_fields)

        # Determinar qué modelos/IDs necesitamos para FKs
        fk_imports, fk_setup = self._build_fk_setup(table)
        fk_imports_str = "\n".join(fk_imports)
        fk_setup_str = "\n        ".join(fk_setup)

        return f"""<?php

namespace Database\\Seeders;

use App\\Models\\{model_name};
{fk_imports_str}
use Illuminate\\Database\\Seeder;
use Illuminate\\Support\\Facades\\DB;

class {seeder_name} extends Seeder
{{
    /**
     * Run the database seeds.
     * Genera 10 registros de prueba para la tabla {table_name}.
     */
    public function run(): void
    {{
        $faker = \\Faker\\Factory::create('es_MX');

        // Precargar IDs de tablas relacionadas
        {fk_setup_str if fk_setup_str.strip() else '// Sin dependencias de FK'}

        for ($i = 0; $i < 10; $i++) {{
            {model_name}::create([
{faker_fields_str}
            ]);
        }}
    }}
}}
"""

    def _build_fk_setup(self, table: Dict):
        """Construye imports y setup para foreign keys"""
        imports = []
        setup = []
        seen_tables = set()

        for rel in self.relationships:
            if rel['source_table'] == table['name'] and rel['target_table']:
                target_table = rel['target_table']
                if target_table in seen_tables:
                    continue
                seen_tables.add(target_table)

                target_model = self._to_studly_case(self._singular(target_table))
                var_ids = f"${self._to_camel_case(target_model)}Ids"

                imports.append(f"use App\\Models\\{target_model};")
                setup.append(
                    f"{var_ids} = {target_model}::pluck('id')->toArray();"
                )

        return imports, setup

    def _build_faker_fields(self, table: Dict) -> List[str]:
        """Genera las líneas de faker para cada campo de la tabla"""
        lines = []

        for col in table['columns']:
            name = col['name']

            # Saltar campos automáticos
            if name in ['id', 'created_at', 'updated_at', 'deleted_at']:
                continue

            # Si es FK, usar pluck de IDs
            fk_rel = self._get_fk_relation(name, table['name'])
            if fk_rel:
                target_model = self._to_studly_case(self._singular(fk_rel['target_table']))
                var_ids = f"${self._to_camel_case(target_model)}Ids"
                is_nullable = not col['not_null']
                if is_nullable:
                    lines.append(
                        f"                '{name}' => !empty({var_ids}) ? $faker->randomElement({var_ids}) : null,"
                    )
                else:
                    lines.append(
                        f"                '{name}' => !empty({var_ids}) ? $faker->randomElement({var_ids}) : 1,"
                    )
                continue

            faker_value = self._get_faker_value(name, col)
            is_nullable = not col['not_null']

            if is_nullable:
                lines.append(
                    f"                '{name}' => $faker->optional()->randomElement([{faker_value}, null]) ?? {faker_value},"
                )
            else:
                lines.append(f"                '{name}' => {faker_value},")

        return lines

    def _get_fk_relation(self, column_name: str, table_name: str):
        """Devuelve la relación FK si la columna es FK, o None"""
        for rel in self.relationships:
            if rel['source_table'] == table_name and column_name in rel.get('source_columns', []):
                return rel
        return None

    def _get_faker_value(self, col_name: str, col: Dict) -> str:
        """
        Decide qué valor de Faker usar basándose en el nombre y tipo de la columna.
        Primero detecta por palabras clave CONTENIDAS en el nombre (contains),
        luego por tipo SQL. Nunca usa lexify — siempre genera palabras reales.
        """
        name_lower = col_name.lower()
        col_type = col['type'].lower()
        base_type = col_type.split('(')[0].strip()

        # ── Detección por palabras clave contenidas en el nombre ──────────
        # Nombres / personas
        if name_lower in ['nombre', 'name', 'nombre_completo', 'full_name', 'nombres']:
            return "$faker->firstName()"
        if 'apellido' in name_lower or name_lower in ['last_name', 'surname']:
            return "$faker->lastName()"
        if name_lower in ['nombre_usuario', 'username', 'user_name', 'nick', 'alias']:
            return "$faker->unique()->userName()"

        # Contacto
        if 'email' in name_lower or 'correo' in name_lower:
            return "$faker->unique()->safeEmail()"
        if 'telefono' in name_lower or 'phone' in name_lower or 'celular' in name_lower \
                or 'movil' in name_lower or name_lower in ['tel', 'fono']:
            return "$faker->phoneNumber()"

        # Ubicación
        if 'direccion' in name_lower or 'address' in name_lower or 'domicilio' in name_lower:
            return "$faker->streetAddress()"
        if 'ciudad' in name_lower or 'city' in name_lower:
            return "$faker->city()"
        if name_lower in ['estado', 'state', 'provincia', 'region']:
            return "$faker->state()"
        if 'pais' in name_lower or 'country' in name_lower:
            return "$faker->country()"
        if 'postal' in name_lower or name_lower in ['cp', 'zip', 'codigo_postal']:
            return "$faker->postcode()"
        if 'colonia' in name_lower or 'barrio' in name_lower or 'neighborhood' in name_lower:
            return "$faker->citySuffix() . ' ' . $faker->city()"
        if 'municipio' in name_lower or 'delegacion' in name_lower:
            return "$faker->city()"

        # Credenciales
        if 'password' in name_lower or 'contrasena' in name_lower or 'contrasenia' in name_lower:
            return "bcrypt($faker->password(8, 16))"
        if 'token' in name_lower or 'api_key' in name_lower:
            return "$faker->sha256()"

        # Dinero
        if 'precio' in name_lower or 'price' in name_lower or 'costo' in name_lower \
                or 'cost' in name_lower or 'monto' in name_lower or 'amount' in name_lower \
                or 'tarifa' in name_lower or 'salario' in name_lower or 'sueldo' in name_lower \
                or 'pago' in name_lower or 'total' in name_lower or 'subtotal' in name_lower \
                or 'descuento' in name_lower or 'impuesto' in name_lower:
            return "$faker->randomFloat(2, 10, 9999)"

        # Fechas
        if 'fecha' in name_lower or ('date' in name_lower and 'update' not in name_lower):
            if 'nacimiento' in name_lower or 'birth' in name_lower:
                return "$faker->date('Y-m-d', '-18 years')"
            if 'inicio' in name_lower or 'start' in name_lower or 'alta' in name_lower:
                return "$faker->dateTimeBetween('-1 year', 'now')->format('Y-m-d')"
            if 'fin' in name_lower or 'end' in name_lower or 'vencimiento' in name_lower \
                    or 'expir' in name_lower:
                return "$faker->dateTimeBetween('now', '+2 years')->format('Y-m-d')"
            return "$faker->date('Y-m-d')"

        # Horas
        if 'hora' in name_lower or ('time' in name_lower and 'datetime' not in name_lower
                                    and 'timestamp' not in name_lower):
            return "$faker->time('H:i:s')"

        # Números / medidas
        if 'edad' in name_lower or name_lower in ['age', 'years', 'anios']:
            return "$faker->numberBetween(1, 99)"
        if 'duracion' in name_lower or 'duration' in name_lower or 'minutos' in name_lower \
                or 'minutes' in name_lower:
            return "$faker->numberBetween(15, 120)"
        if 'cantidad' in name_lower or 'quantity' in name_lower or 'stock' in name_lower \
                or 'capacidad' in name_lower:
            return "$faker->numberBetween(1, 500)"
        if 'numero' in name_lower or 'number' in name_lower or 'num' == name_lower \
                or 'folio' in name_lower:
            return "$faker->numerify('####')"
        if 'calificacion' in name_lower or 'rating' in name_lower or 'puntuacion' in name_lower \
                or 'score' in name_lower:
            return "$faker->numberBetween(1, 10)"
        if 'porcentaje' in name_lower or 'percent' in name_lower:
            return "$faker->numberBetween(0, 100)"

        # Textos descriptivos
        if 'descripcion' in name_lower or 'description' in name_lower or 'detalle' in name_lower \
                or 'nota' in name_lower or 'observacion' in name_lower or 'comentario' in name_lower \
                or 'resumen' in name_lower or 'biografia' in name_lower or 'bio' in name_lower:
            return "$faker->sentence(12)"
        if 'titulo' in name_lower or 'title' in name_lower or 'nombre' in name_lower:
            return "$faker->sentence(3)"
        if 'especialidad' in name_lower or 'specialty' in name_lower or 'profesion' in name_lower \
                or 'profession' in name_lower or 'ocupacion' in name_lower or 'cargo' in name_lower \
                or 'puesto' in name_lower or 'job' in name_lower or 'position' in name_lower:
            return "$faker->jobTitle()"
        if 'empresa' in name_lower or 'company' in name_lower or 'negocio' in name_lower \
                or 'organizacion' in name_lower:
            return "$faker->company()"
        if 'categoria' in name_lower or 'category' in name_lower or 'tipo' in name_lower \
                or 'type' in name_lower or 'clase' in name_lower:
            return "$faker->randomElement(['Tipo A', 'Tipo B', 'Tipo C', 'Especial'])"
        if 'estado' in name_lower or 'status' in name_lower or 'estatus' in name_lower:
            return "$faker->randomElement(['activo', 'inactivo', 'pendiente'])"
        if 'genero' in name_lower or 'gender' in name_lower or 'sexo' in name_lower:
            return "$faker->randomElement(['masculino', 'femenino', 'otro'])"
        if 'color' in name_lower:
            return "$faker->colorName()"

        # Media / archivos
        if 'url' in name_lower or 'link' in name_lower or 'web' in name_lower \
                or 'sitio' in name_lower:
            return "$faker->url()"
        if 'imagen' in name_lower or 'foto' in name_lower or 'image' in name_lower \
                or 'photo' in name_lower or 'avatar' in name_lower:
            return "$faker->imageUrl(640, 480)"
        if 'archivo' in name_lower or 'file' in name_lower or 'documento' in name_lower:
            return "$faker->lexify('doc_??????.pdf')"

        # Identificadores únicos
        if name_lower in ['uuid', 'guid']:
            return "$faker->uuid()"
        if name_lower in ['ip', 'ip_address']:
            return "$faker->ipv4()"
        if 'activo' in name_lower or 'active' in name_lower or 'habilitado' in name_lower \
                or 'enabled' in name_lower or 'visible' in name_lower:
            return "$faker->boolean()"

        # ── Fallback por tipo SQL ─────────────────────────────────────────
        if base_type in ['int', 'integer', 'smallint', 'mediumint']:
            return "$faker->numberBetween(1, 100)"
        if base_type == 'bigint':
            return "$faker->numberBetween(1, 1000)"
        if base_type in ['decimal', 'float', 'double']:
            return "$faker->randomFloat(2, 1, 1000)"
        if base_type in ['varchar', 'char']:
            # Usar palabras reales según el largo del campo
            length = col.get('length', '255')
            try:
                max_len = int(length) if length and str(length).isdigit() else 255
            except (ValueError, TypeError):
                max_len = 255
            if max_len <= 20:
                return "$faker->word()"
            elif max_len <= 60:
                return "$faker->words(2, true)"
            else:
                return "$faker->words(3, true)"
        if base_type == 'text':
            return "$faker->paragraph()"
        if base_type in ['mediumtext', 'longtext']:
            return "$faker->paragraphs(3, true)"
        if base_type == 'boolean':
            return "$faker->boolean()"
        if base_type == 'date':
            return "$faker->date('Y-m-d')"
        if base_type in ['datetime', 'timestamp']:
            return "$faker->dateTime()->format('Y-m-d H:i:s')"
        if base_type == 'time':
            return "$faker->time('H:i:s')"
        if base_type == 'json':
            return "json_encode(['valor' => $faker->word(), 'descripcion' => $faker->sentence()])"

        # Fallback final — siempre palabras reales
        return "$faker->words(2, true)"

    def generate_database_seeder(self):
        """
        Genera el DatabaseSeeder.php respetando el orden de las tablas
        (ya ordenadas por dependencias) y excluyendo users/rol/estatus.
        Las tablas excluidas (que ya tienen sus seeders originales) se llaman primero.
        """
        # Seeders originales que siempre van primero (en el orden del DatabaseSeeder original)
        original_seeders = ['RolSeeder', 'EstatusSeeder', 'UserSeeder']

        # Seeders generados automáticamente (en orden de migración, sin las excluidas)
        generated_seeders = []
        for table in self.tables:
            if table['name'].lower() not in self.SEEDER_EXCLUDED_TABLES:
                model_name = self._to_studly_case(self._singular(table['name']))
                generated_seeders.append(f"{model_name}Seeder")

        # Construir las llamadas
        all_calls = []
        for seeder in original_seeders:
            all_calls.append(f"        $this->call({seeder}::class);")
        for seeder in generated_seeders:
            all_calls.append(f"        $this->call({seeder}::class);")

        calls_str = "\n".join(all_calls)

        content = f"""<?php

namespace Database\\Seeders;

// use Illuminate\\Database\\Console\\Seeds\\WithoutModelEvents;
use Illuminate\\Database\\Seeder;

class DatabaseSeeder extends Seeder
{{
    /**
     * Seed the application's database.
     * Orden: tablas base → tablas con dependencias (respeta FK order).
     */
    public function run(): void
    {{
{calls_str}
    }}
}}
"""

        filepath = f"{self.output_dir}/seeders/DatabaseSeeder.php"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✓ DatabaseSeeder.php generado con {len(all_calls)} seeders en orden correcto")

    # -------------------------------------------------------------------------
    # ROUTES
    # -------------------------------------------------------------------------

    def generate_routes(self):
        """Genera el archivo de rutas API"""
        routes = []

        for table in self.tables:
            model_name = self._to_studly_case(self._singular(table['name']))
            controller_name = f"{model_name}Controller"
            route_name = self._to_kebab_case(table['name'])

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

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _to_studly_case(self, string: str) -> str:
        return ''.join(word.capitalize() for word in string.replace('_', ' ').split())

    def _to_camel_case(self, string: str) -> str:
        studly = self._to_studly_case(string)
        return studly[0].lower() + studly[1:] if studly else ''

    def _to_kebab_case(self, string: str) -> str:
        return string.replace('_', '-').lower()

    def _singular(self, word: str) -> str:
        """Intenta singularizar una palabra (incluye español)"""
        word_lower = word.lower()

        irregulars_es = {
            'clientes': 'cliente',
            'medicos': 'medico',
            'servicios': 'servicio',
            'horarios': 'horario',
            'estatus': 'estatus',
            'roles': 'rol',
            'users': 'user',
        }

        if word_lower in irregulars_es:
            result = irregulars_es[word_lower]
            if word[0].isupper():
                result = result.capitalize()
            return result

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

    print("Parseando archivo .mwb...")
    parser = WorkbenchParser(mwb_file)
    if not parser.parse():
        print("Error al parsear el archivo")
        sys.exit(1)

    print(f"✓ Se encontraron {len(parser.tables)} tablas")
    print(f"✓ Se encontraron {len(parser.relationships)} relaciones\n")

    print("Generando archivos Laravel...")
    generator = LaravelGenerator(parser.tables, parser.relationships, output_dir)
    generator.generate_all()


if __name__ == '__main__':
    main()