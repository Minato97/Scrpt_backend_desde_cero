#!/usr/bin/env python3
"""
Laravel Backend Complete Setup
Crea proyecto Laravel con Docker + genera backend desde modelo Workbench
"""

import os
import re
import subprocess
import shutil
import zipfile
import sys
import time
from pathlib import Path

ZIP_DEFAULT = "backend-repo.zip"
GENERATOR_SCRIPT = "laravel_generator.py"

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def abort(msg):
    print_error(f"ERROR: {msg}")
    print(f"{Colors.RED}🛑 Proceso abortado.{Colors.END}")
    sys.exit(1)

def run(cmd, cwd=None, capture=False):
    """Ejecuta un comando"""
    try:
        if capture:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            if result.returncode != 0:
                abort(f"Error ejecutando: {' '.join(cmd)}\n{result.stderr}")
            return result.stdout
        else:
            result = subprocess.run(cmd, cwd=cwd)
            if result.returncode != 0:
                abort(f"Error ejecutando: {' '.join(cmd)}")
    except Exception as e:
        abort(f"Error ejecutando comando: {e}")

def check_requirements():
    """Verifica que estén instaladas las dependencias"""
    print_header("VERIFICANDO REQUISITOS")
    
    requirements = {
        'Docker': ['docker', '--version'],
        'Docker Compose': ['docker', 'compose', 'version'],
        'Python': ['python3', '--version'],
        'Git': ['git', '--version']
    }
    
    missing = []
    for name, cmd in requirements.items():
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print_success(f"{name} instalado")
        except:
            print_error(f"{name} NO encontrado")
            missing.append(name)
    
    if missing:
        abort(f"Faltan dependencias: {', '.join(missing)}")
    
    # Verificar archivos necesarios
    if not os.path.isfile(ZIP_DEFAULT):
        abort(f"No se encontró {ZIP_DEFAULT} en el directorio actual")
    print_success(f"{ZIP_DEFAULT} encontrado")
    
    if not os.path.isfile(GENERATOR_SCRIPT):
        abort(f"No se encontró {GENERATOR_SCRIPT} en el directorio actual")
    print_success(f"{GENERATOR_SCRIPT} encontrado")

def get_user_input():
    """Obtiene información del usuario"""
    print_header("CONFIGURACIÓN DEL PROYECTO")
    
    project_name = input(f"{Colors.BOLD}📁 Nombre del proyecto Laravel: {Colors.END}").strip()
    if not project_name:
        abort("El nombre del proyecto es requerido")
    
    db_name = input(f"{Colors.BOLD}🛢  Nombre de la base de datos: {Colors.END}").strip()
    if not db_name:
        db_name = project_name
        print_info(f"Usando '{db_name}' como nombre de BD")
    
    db_port = input(f"{Colors.BOLD}🐳 Puerto MySQL (default: 3307): {Colors.END}").strip()
    if not db_port:
        db_port = "3307"
        print_info(f"Usando puerto {db_port}")

    # Solicitar archivo .mwb OBLIGATORIO
    while True:
        workbench_file = input(
            f"{Colors.BOLD}📐 Ruta completa del archivo .mwb de Workbench (OBLIGATORIO): {Colors.END}"
        ).strip()

        workbench_file = workbench_file.replace('"', '').replace("'", "")

        if not workbench_file:
            print_error("Debes proporcionar un archivo .mwb válido.")
            continue

        if not os.path.exists(workbench_file):
            print_error(f"Archivo no encontrado: {workbench_file}")
            print_warning("Intenta nuevamente...\n")
            continue

        if not workbench_file.lower().endswith(".mwb"):
            print_error("El archivo debe tener extensión .mwb")
            print_warning("Intenta nuevamente...\n")
            continue

        print_success("Archivo .mwb encontrado")
        break
    
    repo_url = input(f"{Colors.BOLD}📡 URL del repositorio Git (opcional): {Colors.END}").strip()
    
    return {
        'project_name': project_name,
        'db_name': db_name,
        'db_port': db_port,
        'workbench_file': workbench_file,
        'repo_url': repo_url
    }

def setup_laravel_project(config):
    """Configura el proyecto Laravel con Docker"""
    print_header("FASE 1: CONFIGURANDO PROYECTO LARAVEL")
    
    project_name = config['project_name']
    db_name = config['db_name']
    db_port = config['db_port']
    
    # Crear carpeta del proyecto
    print_info(f"Creando directorio {project_name}...")
    os.makedirs(project_name, exist_ok=True)
    
    # Descomprimir
    print_info("Descomprimiendo proyecto base...")
    with zipfile.ZipFile(ZIP_DEFAULT, 'r') as zip_ref:
        zip_ref.extractall(project_name)
    print_success("Proyecto descomprimido")
    
    # Cambiar al directorio del proyecto
    os.chdir(project_name)
    
    # Detectar y aplanar estructura
    items = os.listdir(".")
    folders = [f for f in items if os.path.isdir(f)]
    
    if len(folders) == 1:
        inner = folders[0]
        print_info(f"Aplanando estructura desde {inner}/...")
        for item in os.listdir(inner):
            src = os.path.join(inner, item)
            dst = item
            if os.path.exists(dst):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                else:
                    os.remove(dst)
            shutil.move(src, dst)
        shutil.rmtree(inner)
    
    if not os.path.exists("docker-compose.yml"):
        abort("No se encontró docker-compose.yml en el proyecto")
    
    # Eliminar container_name del docker-compose
    print_info("Configurando docker-compose.yml...")
    with open("docker-compose.yml", "r") as f:
        lines = f.readlines()
    
    with open("docker-compose.yml", "w") as f:
        for line in lines:
            if "container_name" not in line:
                f.write(line)
    
    # Configurar base de datos y puerto
    with open("docker-compose.yml", "r") as f:
        content = f.read()
    
    content = content.replace("MYSQL_DATABASE: laravel_backend",
                              f"MYSQL_DATABASE: {db_name}")
    content = content.replace('"3306:3306"', f'"{db_port}:3306"')
    
    with open("docker-compose.yml", "w") as f:
        f.write(content)
    
    print_success("docker-compose.yml configurado")
    
    # Configurar .env
    print_info("Configurando .env...")
    if not os.path.exists(".env.example"):
        abort("No existe .env.example en el proyecto")
    
    shutil.copy(".env.example", ".env")
    
    with open(".env", "r") as f:
        env = f.read()
    
    env = re.sub(r"DB_USERNAME=.*", "DB_USERNAME=laravel", env)
    env = re.sub(r"DB_PASSWORD=.*", "DB_PASSWORD=root", env)
    env = re.sub(r"DB_DATABASE=.*", f"DB_DATABASE={db_name}", env)
    env = re.sub(r"DB_HOST=.*", "DB_HOST=db", env)
    env = re.sub(r"DB_PORT=.*", "DB_PORT=3306", env)
    
    with open(".env", "w") as f:
        f.write(env)
    
    print_success("Archivo .env configurado")
    
    return os.getcwd()

def start_docker_containers(config):
    """Inicia los contenedores Docker"""
    print_header("FASE 2: INICIANDO CONTENEDORES DOCKER")
    
    project_name = config['project_name']
    db_name = config['db_name']
    
    # Levantar contenedores
    print_info("Construyendo y levantando contenedores...")
    run(["docker", "compose", "-p", project_name, "up", "-d", "--build"])
    print_success("Contenedores iniciados")
    
    # Esperar MySQL
    print_info("Esperando que MySQL esté listo...")
    max_attempts = 30
    attempt = 0
    
    while attempt < max_attempts:
        try:
            result = subprocess.run(
                ["docker", "compose", "-p", project_name, "exec", "-T", "db",
                 "mysqladmin", "ping", "-h", "localhost", "-uroot", "-proot"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            if b"mysqld is alive" in result.stdout:
                break
        except:
            pass
        
        attempt += 1
        time.sleep(2)
        print(f"  Intento {attempt}/{max_attempts}...", end='\r')
    
    if attempt >= max_attempts:
        abort("MySQL no respondió después de 60 segundos")
    
    print_success("MySQL está listo                    ")
    
    # Crear base de datos
    print_info("Creando base de datos...")
    run([
        "docker", "compose", "-p", project_name,
        "exec", "-T", "db",
        "mysql", "-uroot", "-proot",
        "-e", f"CREATE DATABASE IF NOT EXISTS {db_name};"
    ])
    
    # Dar permisos
    print_info("Configurando permisos...")
    run([
        "docker", "compose", "-p", project_name,
        "exec", "-T", "db",
        "mysql", "-uroot", "-proot",
        "-e", f"GRANT ALL PRIVILEGES ON {db_name}.* TO 'laravel'@'%'; FLUSH PRIVILEGES;"
    ])
    
    print_success("Base de datos configurada")
    
    # Obtener ID del contenedor app
    result = subprocess.check_output(
        ["docker", "compose", "-p", project_name, "ps", "-q", "app"]
    ).decode().strip()
    
    if not result:
        abort("No se encontró el contenedor app")
    
    return result

def setup_laravel_app(config, app_container):
    """Configura la aplicación Laravel"""
    print_header("FASE 3: CONFIGURANDO APLICACIÓN LARAVEL")
    
    # Composer
    print_info("Instalando dependencias con Composer...")
    run(["docker", "exec", app_container, "composer", "update"])
    print_success("Dependencias instaladas")
    
    # Artisan commands
    print_info("Generando APP_KEY...")
    run(["docker", "exec", app_container, "php", "artisan", "key:generate"])
    
    print_info("Generando JWT_SECRET...")
    run(["docker", "exec", app_container, "php", "artisan", "jwt:secret"])
    
    print_success("Claves generadas")

def generate_backend_from_workbench(config, project_path, app_container):
    """Genera el backend desde el modelo de Workbench"""
    if not config.get('workbench_file'):
        print_warning("No se proporcionó archivo .mwb, saltando generación de backend")
        return False
    
    print_header("FASE 4: GENERANDO BACKEND DESDE WORKBENCH")
    
    workbench_file = config['workbench_file']
    temp_output = "/tmp/laravel_generated"
    
    # Regresar al directorio original donde está el script
    original_dir = Path(__file__).parent.absolute()
    
    print_info(f"Generando backend desde {Path(workbench_file).name}...")
    
    # Ejecutar el generador
    try:
        os.chdir(original_dir)
        run([
            "python3", GENERATOR_SCRIPT,
            workbench_file,
            temp_output
        ])
        print_success("Backend generado exitosamente")
    except Exception as e:
        print_error(f"Error generando backend: {e}")
        os.chdir(project_path)
        return False
    
    # Regresar al proyecto
    os.chdir(project_path)
    
    # Copiar archivos generados
    print_info("Copiando archivos al proyecto...")
    
    # Copiar migraciones
    migrations_src = os.path.join(temp_output, "migrations")
    migrations_dst = "database/migrations"
    
    if os.path.exists(migrations_src):
        for file in os.listdir(migrations_src):
            src_file = os.path.join(migrations_src, file)
            dst_file = os.path.join(migrations_dst, file)
            shutil.copy2(src_file, dst_file)
        print_success(f"✓ Migraciones copiadas ({len(os.listdir(migrations_src))} archivos)")
    
    # Copiar modelos
    models_src = os.path.join(temp_output, "models")
    models_dst = "app/Models"
    
    if os.path.exists(models_src):
        os.makedirs(models_dst, exist_ok=True)
        for file in os.listdir(models_src):
            src_file = os.path.join(models_src, file)
            dst_file = os.path.join(models_dst, file)
            shutil.copy2(src_file, dst_file)
        print_success(f"✓ Modelos copiados ({len(os.listdir(models_src))} archivos)")
    
    # Copiar controladores
    controllers_src = os.path.join(temp_output, "controllers")
    controllers_dst = "app/Http/Controllers/Api"
    
    if os.path.exists(controllers_src):
        os.makedirs(controllers_dst, exist_ok=True)
        for file in os.listdir(controllers_src):
            src_file = os.path.join(controllers_src, file)
            dst_file = os.path.join(controllers_dst, file)
            shutil.copy2(src_file, dst_file)
        print_success(f"✓ Controladores copiados ({len(os.listdir(controllers_src))} archivos)")
    
    # Agregar rutas
    routes_src = os.path.join(temp_output, "routes/api.php")
    routes_dst = "routes/api.php"
    
    if os.path.exists(routes_src):
        with open(routes_src, 'r') as f:
            new_routes = f.read()
        
        # Leer rutas existentes
        with open(routes_dst, 'r') as f:
            existing_routes = f.read()
        
        # Agregar solo las nuevas rutas (después de los imports)
        lines = new_routes.split('\n')
        route_lines = [line for line in lines if line.strip().startswith('Route::')]
        
        if route_lines:
            with open(routes_dst, 'a') as f:
                f.write("\n\n// Rutas generadas automáticamente\n")
                f.write('\n'.join(route_lines))
        
        print_success(f"✓ Rutas agregadas")
    
    # Ejecutar migraciones
    print_info("Ejecutando migraciones...")

    result = subprocess.run(
        ["docker", "exec", app_container, "php", "artisan", "migrate:fresh", "--seed"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print_error("❌ ERROR en migraciones:")
        print(result.stderr)
        return False
    else:
        print_success("✓ Migraciones ejecutadas correctamente")
    
    # Limpiar archivos temporales
    if os.path.exists(temp_output):
        shutil.rmtree(temp_output)
    
    return True

def initialize_git_repo(config, project_path):
    """Inicializa y sube el repositorio a Git"""
    repo_url = config.get('repo_url')
    
    if not repo_url:
        print_warning("No se proporcionó URL de repositorio, saltando configuración Git")
        return
    
    print_header("FASE 5: CONFIGURANDO REPOSITORIO GIT")
    
    os.chdir(project_path)
    
    # Eliminar .git si existe
    if os.path.exists(".git"):
        shutil.rmtree(".git")
    
    print_info("Inicializando repositorio...")
    run(["git", "init"])
    run(["git", "add", "."])
    run(["git", "commit", "-m", "Initial backend setup with auto-generated code"])
    
    print_info(f"Conectando con {repo_url}...")
    run(["git", "remote", "add", "origin", repo_url])
    run(["git", "branch", "-M", "main"])
    
    print_info("Subiendo código...")
    run(["git", "push", "-u", "origin", "main", "--force"])
    
    print_success("Repositorio configurado y código subido")

def print_final_summary(config, backend_generated):
    """Imprime resumen final"""
    print_header("RESUMEN FINAL")
    
    project_name = config['project_name']
    db_port = config['db_port']
    
    print(f"{Colors.BOLD}Proyecto:{Colors.END} {project_name}")
    print(f"{Colors.BOLD}Base de datos:{Colors.END} {config['db_name']}")
    print(f"{Colors.BOLD}Puerto MySQL:{Colors.END} {db_port}")
    
    if backend_generated:
        print(f"{Colors.BOLD}Backend generado:{Colors.END} {Colors.GREEN}SÍ{Colors.END}")
    else:
        print(f"{Colors.BOLD}Backend generado:{Colors.END} {Colors.YELLOW}NO{Colors.END}")
    
    if config.get('repo_url'):
        print(f"{Colors.BOLD}Repositorio:{Colors.END} {config['repo_url']}")
    
    print(f"\n{Colors.BOLD}🌐 URLs de Acceso:{Colors.END}")
    print(f"  • API:        http://localhost:8000")
    print(f"  • phpMyAdmin: http://localhost:8080")
    print(f"  • MySQL:      localhost:{db_port}")
    
    print(f"\n{Colors.BOLD}📝 Comandos útiles:{Colors.END}")
    print(f"  • Ver logs:     docker compose -p {project_name} logs -f")
    print(f"  • Detener:      docker compose -p {project_name} down")
    print(f"  • Reiniciar:    docker compose -p {project_name} restart")
    print(f"  • Entrar a app: docker compose -p {project_name} exec app bash")
    
    if backend_generated:
        print(f"\n{Colors.BOLD}✨ Tu backend está listo con:{Colors.END}")
        print(f"  ✅ Migraciones ejecutadas")
        print(f"  ✅ Modelos con relaciones")
        print(f"  ✅ Controladores API con CRUD")
        print(f"  ✅ Rutas configuradas")

def main():
    """Función principal"""
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                                                                ║")
    print("║    🚀 Laravel Backend Complete Setup                          ║")
    print("║    Docker + Auto-Generated Code from Workbench                ║")
    print("║                                                                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    try:
        # Verificar requisitos
        check_requirements()
        
        # Obtener configuración del usuario
        config = get_user_input()
        
        # Confirmar
        print(f"\n{Colors.BOLD}¿Continuar con la configuración? (s/n): {Colors.END}", end='')
        if input().lower() not in ['s', 'si', 'y', 'yes']:
            print_warning("Operación cancelada por el usuario")
            sys.exit(0)
        
        # Fase 1: Setup Laravel
        project_path = setup_laravel_project(config)
        
        # Fase 2: Docker
        app_container = start_docker_containers(config)
        
        # Fase 3: Laravel setup
        setup_laravel_app(config, app_container)
        
        # Fase 4: Generar backend desde Workbench
        backend_generated = generate_backend_from_workbench(config, project_path, app_container)
        
        # Fase 5: Git (opcional)
        initialize_git_repo(config, project_path)
        
        # Resumen final
        print_final_summary(config, backend_generated)
        
        print(f"\n{Colors.BOLD}{Colors.GREEN}✅ ¡PROCESO COMPLETADO EXITOSAMENTE! 🎉{Colors.END}\n")
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  Proceso interrumpido por el usuario{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
