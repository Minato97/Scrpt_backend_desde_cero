#!/usr/bin/env python3
"""
Utilidades y helpers para el generador Laravel
Funciones auxiliares para conversión de nombres, validación, etc.
"""

import re
from typing import Dict, List, Optional


class NamingHelper:
    """Helper para conversión de nombres entre diferentes convenciones"""
    
    @staticmethod
    def to_studly_case(string: str) -> str:
        """Convierte a StudlyCase/PascalCase
        
        Ejemplos:
            user_posts -> UserPosts
            blog-posts -> BlogPosts
            user posts -> UserPosts
        """
        # Reemplazar separadores con espacios
        string = re.sub(r'[-_\s]+', ' ', string)
        # Capitalizar cada palabra y juntar
        return ''.join(word.capitalize() for word in string.split())
    
    @staticmethod
    def to_camel_case(string: str) -> str:
        """Convierte a camelCase
        
        Ejemplos:
            user_posts -> userPosts
            blog-posts -> blogPosts
            UserPosts -> userPosts
        """
        studly = NamingHelper.to_studly_case(string)
        return studly[0].lower() + studly[1:] if studly else ''
    
    @staticmethod
    def to_snake_case(string: str) -> str:
        """Convierte a snake_case
        
        Ejemplos:
            UserPosts -> user_posts
            blogPosts -> blog_posts
            user-posts -> user_posts
        """
        # Insertar guión bajo antes de mayúsculas
        string = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', string)
        string = re.sub('([a-z0-9])([A-Z])', r'\1_\2', string)
        # Reemplazar guiones con guiones bajos
        string = string.replace('-', '_')
        return string.lower()
    
    @staticmethod
    def to_kebab_case(string: str) -> str:
        """Convierte a kebab-case
        
        Ejemplos:
            UserPosts -> user-posts
            user_posts -> user-posts
            blogPosts -> blog-posts
        """
        return NamingHelper.to_snake_case(string).replace('_', '-')
    
    @staticmethod
    def to_plural(word: str) -> str:
        """Pluraliza una palabra en inglés (reglas básicas)
        
        Ejemplos:
            user -> users
            post -> posts
            category -> categories
            company -> companies
        """
        # Reglas especiales
        irregulars = {
            'person': 'people',
            'man': 'men',
            'woman': 'women',
            'child': 'children',
            'tooth': 'teeth',
            'foot': 'feet',
            'mouse': 'mice',
            'goose': 'geese',
        }
        
        word_lower = word.lower()
        if word_lower in irregulars:
            return irregulars[word_lower]
        
        # Termina en y precedida de consonante
        if word.endswith('y') and len(word) > 1 and word[-2] not in 'aeiou':
            return word[:-1] + 'ies'
        
        # Termina en s, x, z, ch, sh
        if word.endswith(('s', 'ss', 'x', 'z', 'ch', 'sh')):
            return word + 'es'
        
        # Termina en f o fe
        if word.endswith('f'):
            return word[:-1] + 'ves'
        if word.endswith('fe'):
            return word[:-2] + 'ves'
        
        # Regla por defecto
        return word + 's'
    
    @staticmethod
    def to_singular(word: str) -> str:
        """Singulariza una palabra en inglés (reglas básicas)
        
        Ejemplos:
            users -> user
            posts -> post
            categories -> category
            companies -> company
        """
        # Reglas especiales inversas
        irregulars = {
            'people': 'person',
            'men': 'man',
            'women': 'woman',
            'children': 'child',
            'teeth': 'tooth',
            'feet': 'foot',
            'mice': 'mouse',
            'geese': 'goose',
        }
        
        word_lower = word.lower()
        if word_lower in irregulars:
            return irregulars[word_lower]
        
        # Termina en ies
        if word.endswith('ies') and len(word) > 3:
            return word[:-3] + 'y'
        
        # Termina en ves
        if word.endswith('ves'):
            return word[:-3] + 'f'
        
        # Termina en ses, xes, zes, ches, shes
        if word.endswith(('ses', 'xes', 'zes', 'ches', 'shes')):
            return word[:-2]
        
        # Termina en s
        if word.endswith('s') and len(word) > 1:
            return word[:-1]
        
        return word


class ValidationHelper:
    """Helper para generar reglas de validación"""
    
    TYPE_RULES = {
        'int': 'integer',
        'tinyint': 'integer',
        'smallint': 'integer',
        'mediumint': 'integer',
        'bigint': 'integer',
        'varchar': 'string',
        'char': 'string',
        'text': 'string',
        'mediumtext': 'string',
        'longtext': 'string',
        'decimal': 'numeric',
        'float': 'numeric',
        'double': 'numeric',
        'boolean': 'boolean',
        'date': 'date',
        'datetime': 'date',
        'timestamp': 'date',
        'time': 'date_format:H:i:s',
        'json': 'array',
    }
    
    @staticmethod
    def get_validation_rule(column: Dict, relationships: List[Dict] = None) -> str:
        """Genera regla de validación para una columna"""
        rules = []
        
        # Required/Nullable
        if column['not_null']:
            rules.append('required')
        else:
            rules.append('nullable')
        
        # Tipo
        col_type = column['type'].lower()
        if col_type in ValidationHelper.TYPE_RULES:
            rules.append(ValidationHelper.TYPE_RULES[col_type])
        
        # Longitud para strings
        if col_type in ['varchar', 'char'] and column['length']:
            rules.append(f"max:{column['length']}")
        
        # Foreign key validation
        if relationships:
            for rel in relationships:
                if column['name'] in rel.get('source_columns', []):
                    target_table = rel['target_table']
                    target_col = rel['target_columns'][0] if rel['target_columns'] else 'id'
                    rules.append(f"exists:{target_table},{target_col}")
                    break
        
        return '|'.join(rules)


class DocblockHelper:
    """Helper para generar docblocks PHPDoc"""
    
    @staticmethod
    def generate_class_docblock(class_name: str, description: str = None) -> str:
        """Genera docblock para una clase"""
        desc = description or f"{class_name} model"
        return f"""/**
 * {desc}
 *
 * @package App\\Models
 */"""
    
    @staticmethod
    def generate_method_docblock(method_name: str, params: List[Dict] = None, 
                                 return_type: str = None, description: str = None) -> str:
        """Genera docblock para un método"""
        lines = ["/**"]
        
        if description:
            lines.append(f" * {description}")
            lines.append(" *")
        
        if params:
            for param in params:
                param_type = param.get('type', 'mixed')
                param_name = param.get('name', '')
                param_desc = param.get('description', '')
                lines.append(f" * @param {param_type} ${param_name} {param_desc}")
        
        if return_type:
            lines.append(f" * @return {return_type}")
        
        lines.append(" */")
        return "\n".join(lines)
    
    @staticmethod
    def generate_property_docblock(property_name: str, prop_type: str, 
                                   description: str = None) -> str:
        """Genera docblock para una propiedad"""
        desc = description or f"The {property_name}"
        return f"""    /**
     * {desc}
     *
     * @var {prop_type}
     */"""


class TypeMapper:
    """Helper para mapeo de tipos entre diferentes sistemas"""
    
    MYSQL_TO_LARAVEL = {
        'int': 'integer',
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
        'tinyint(1)': 'boolean',
        'date': 'date',
        'datetime': 'dateTime',
        'timestamp': 'timestamp',
        'time': 'time',
        'year': 'year',
        'json': 'json',
        'enum': 'enum',
        'blob': 'binary',
    }
    
    MYSQL_TO_PHP = {
        'int': 'int',
        'tinyint': 'int',
        'smallint': 'int',
        'mediumint': 'int',
        'bigint': 'int',
        'varchar': 'string',
        'char': 'string',
        'text': 'string',
        'mediumtext': 'string',
        'longtext': 'string',
        'decimal': 'float',
        'float': 'float',
        'double': 'float',
        'boolean': 'bool',
        'tinyint(1)': 'bool',
        'date': 'string',
        'datetime': 'string',
        'timestamp': 'string',
        'time': 'string',
        'json': 'array',
    }
    
    @staticmethod
    def mysql_to_laravel(mysql_type: str) -> str:
        """Convierte tipo MySQL a tipo de migración Laravel"""
        mysql_type = mysql_type.lower().strip()
        return TypeMapper.MYSQL_TO_LARAVEL.get(mysql_type, 'string')
    
    @staticmethod
    def mysql_to_php(mysql_type: str) -> str:
        """Convierte tipo MySQL a tipo PHP"""
        mysql_type = mysql_type.lower().strip()
        return TypeMapper.MYSQL_TO_PHP.get(mysql_type, 'mixed')
    
    @staticmethod
    def should_cast(column: Dict) -> Optional[str]:
        """Determina si una columna debe tener cast y de qué tipo"""
        col_type = column['type'].lower()
        
        cast_map = {
            'datetime': 'datetime',
            'timestamp': 'datetime',
            'date': 'date',
            'json': 'array',
            'boolean': 'boolean',
            'tinyint(1)': 'boolean',
            'int': 'integer',
            'tinyint': 'integer',
            'smallint': 'integer',
            'mediumint': 'integer',
            'bigint': 'integer',
            'decimal': 'decimal:2',
            'float': 'float',
            'double': 'double',
        }
        
        return cast_map.get(col_type)


class FileHelper:
    """Helper para operaciones con archivos"""
    
    @staticmethod
    def ensure_directory(path: str) -> bool:
        """Asegura que un directorio existe, creándolo si es necesario"""
        import os
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creando directorio {path}: {e}")
            return False
    
    @staticmethod
    def write_file(filepath: str, content: str, encoding: str = 'utf-8') -> bool:
        """Escribe contenido a un archivo"""
        try:
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error escribiendo archivo {filepath}: {e}")
            return False
    
    @staticmethod
    def read_file(filepath: str, encoding: str = 'utf-8') -> Optional[str]:
        """Lee contenido de un archivo"""
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except Exception as e:
            print(f"Error leyendo archivo {filepath}: {e}")
            return None


class TemplateHelper:
    """Helper para templates de código"""
    
    @staticmethod
    def indent(text: str, spaces: int = 4) -> str:
        """Indenta texto con el número especificado de espacios"""
        indent_str = ' ' * spaces
        return '\n'.join(indent_str + line if line.strip() else line 
                        for line in text.split('\n'))
    
    @staticmethod
    def format_array(items: List[str], indent: int = 8, quotes: bool = True) -> str:
        """Formatea un array PHP con items en múltiples líneas"""
        if not items:
            return ""
        
        indent_str = ' ' * indent
        quote = "'" if quotes else ""
        
        formatted_items = [f"{indent_str}{quote}{item}{quote}" for item in items]
        return ",\n".join(formatted_items)
    
    @staticmethod
    def format_associative_array(items: Dict[str, str], indent: int = 8) -> str:
        """Formatea un array asociativo PHP"""
        if not items:
            return ""
        
        indent_str = ' ' * indent
        formatted_items = [f"{indent_str}'{key}' => '{value}'" 
                          for key, value in items.items()]
        return ",\n".join(formatted_items)


# Funciones de utilidad standalone

def is_foreign_key(column_name: str) -> bool:
    """Detecta si una columna es probablemente una foreign key"""
    return column_name.endswith('_id') and column_name != 'id'


def get_foreign_table_name(column_name: str) -> str:
    """Obtiene el nombre de la tabla desde un nombre de FK"""
    if column_name.endswith('_id'):
        singular = column_name[:-3]  # Remover '_id'
        return NamingHelper.to_plural(singular)
    return ''


def is_timestamp_column(column_name: str) -> bool:
    """Detecta si una columna es un timestamp especial de Laravel"""
    return column_name in ['created_at', 'updated_at', 'deleted_at', 'email_verified_at']


def sanitize_php_variable(name: str) -> str:
    """Sanitiza un nombre para usarlo como variable PHP"""
    # Remover caracteres no válidos
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    # Asegurar que no empiece con número
    if name and name[0].isdigit():
        name = '_' + name
    return name


def format_php_value(value: any, value_type: str = 'string') -> str:
    """Formatea un valor para usarlo en código PHP"""
    if value is None:
        return 'null'
    
    if value_type in ['string', 'text']:
        # Escapar comillas simples
        value = str(value).replace("'", "\\'")
        return f"'{value}'"
    elif value_type in ['integer', 'int', 'boolean', 'bool']:
        return str(value)
    elif value_type == 'array':
        return '[]'
    else:
        return f"'{value}'"


# Exportar clases y funciones principales
__all__ = [
    'NamingHelper',
    'ValidationHelper',
    'DocblockHelper',
    'TypeMapper',
    'FileHelper',
    'TemplateHelper',
    'is_foreign_key',
    'get_foreign_table_name',
    'is_timestamp_column',
    'sanitize_php_variable',
    'format_php_value',
]
