import math
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import time
import pickle
import os
import threading
import matplotlib.pyplot as plt
import pandas as pd
from collections import Counter

from dotenv import load_dotenv
import os

# Cargar variables desde el archivo .env
load_dotenv()

INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
INSTAGRAM_PASS = os.getenv("INSTAGRAM_PASS")
USUARIO_OBJETIVO = os.getenv("USUARIO_OBJETIVO")

# =====================================================
# 🔧 CONFIGURACIONES GLOBALES
# =====================================================

# Archivo donde se guardarán las cookies de sesión
COOKIES_FILE = "cookies.pkl"

# Número de hilos (grupos de trabajo)
NUMERO_HILOS = 4  # 👈 cámbialo aquí para ajustar la cantidad de hilos dinámicamente

# Diccionario dinámico según el número de hilos
Division_Seguidores = {f"V{i+1}": [] for i in range(NUMERO_HILOS)}

# Diccionario global para guardar resultados
Lista_Seguidores_Cantidad = {}

# Lock para evitar conflictos entre hilos
lock = threading.Lock()  # 🔒 evita conflictos entre hilos al escribir en el diccionario


# =====================================================
# 🚀 PASO 1: CREACIÓN DEL NAVEGADOR Y EVASIÓN DE DETECCIÓN
# =====================================================

def crear_navegador():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)

    # === EVADIR DETECCIÓN ===
    stealth(driver,
            languages=["es-ES", "es"],
            vendor="Google Inc.",
            platform="Win64",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
    )

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
    })
    return driver

# =====================================================
# 🍪 PASO 2: GESTIÓN DE COOKIES (Guardar / Cargar Sesión)
# =====================================================

# === GUARDAR Y CARGAR COOKIES ===
def guardar_cookies(driver, path=COOKIES_FILE):
    with open(path, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    print("✅ Cookies guardadas.")

def cargar_cookies(driver, path=COOKIES_FILE):
    if not os.path.exists(path):
        return False
    driver.get("https://www.instagram.com/")
    time.sleep(2)
    with open(path, "rb") as f:
        cookies = pickle.load(f)
    for cookie in cookies:
        cookie.pop("sameSite", None)
        cookie.pop("expiry", None)
        try:
            driver.add_cookie(cookie)
        except:
            pass
    driver.refresh()
    time.sleep(3)
    print("✅ Sesión restaurada desde cookies.")
    return True


# =====================================================
# 🔑 PASO 3: LOGIN AUTOMÁTICO (SOLO SI NO EXISTEN COOKIES)
# =====================================================

# === LOGIN SOLO SI NO EXISTEN COOKIES ===
def login(driver):
    driver.get("https://www.instagram.com/")
    time.sleep(5)

    print("Iniciando sesión...")
    try:
        username = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        password = driver.find_element(By.NAME, "password")

        username.send_keys(INSTAGRAM_USER)
        password.send_keys(INSTAGRAM_PASS)

        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(8)

        # "Guardar info" → No
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Ahora no']"))
            ).click()
        except:
            pass

        print("✅ Login exitoso.")
        guardar_cookies(driver)

    except Exception as e:
        print("Error login:", e)

# =====================================================
# 👥 PASO 4: ABRIR PERFIL Y MODAL DE SEGUIDORES
# =====================================================

# === IR AL PERFIL Y ABRIR SEGUIDORES ===
def abrir_seguidores(driver, usuario=USUARIO_OBJETIVO):
    driver.get(f"https://www.instagram.com/{usuario}/")
    time.sleep(5)

    try:
        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/followers/')]"))
        )
        btn.click()
        print("Modal de seguidores abierto.")
        time.sleep(4)  # Esperar carga
        return True
    except Exception as e:
        print("No se pudo abrir:", e)
        return False

# =====================================================
# 📜 PASO 5: SCROLL EN EL MODAL DE SEGUIDORES
# =====================================================

def hacer_scroll_y_extraer(driver):
    div_scroll = driver.find_element(By.XPATH,
        '/html/body/div[4]/div[2]/div/div/div[1]/div/div[2]/div/div/div/div/div[2]/div/div/div[3]'
    )

    scroll_height = driver.execute_script("return arguments[0].scrollHeight", div_scroll)
    client_height = driver.execute_script("return arguments[0].clientHeight", div_scroll)
    print("ScrollHeight:", scroll_height, "ClientHeight:", client_height)

    last_height = 0
    while True:
        driver.execute_script("arguments[0].scrollTop += arguments[0].clientHeight;", div_scroll)
        time.sleep(10)

        new_scroll = driver.execute_script("return arguments[0].scrollTop;", div_scroll)
        scroll_height = driver.execute_script("return arguments[0].scrollHeight;", div_scroll)

        if abs(scroll_height - new_scroll - div_scroll.size['height']) < 5 or new_scroll == last_height:
            break
        last_height = new_scroll

    print("✅ Llegó al final del scroll.")
    return True


# =====================================================
# 🧩 PASO 6: EXTRAER SEGUIDORES VISIBLES Y DIVIDIRLOS EN GRUPOS
# =====================================================

def extraer_visibles(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[@dir='auto' and contains(@class, '_ap3a')]"))
        )

        nombres = driver.find_elements(
            By.XPATH,
            "//span[@dir='auto' and contains(@class, '_ap3a')]"
        )

        seguidores = set()
        for span in nombres:
            texto = span.text.strip()
            if texto and len(texto) > 1:
                seguidores.add(texto)

        # 🔹 Convertir a lista ordenada
        seguidores = sorted(list(seguidores))

        print(f"\n{len(seguidores)} seguidores visibles extraídos:")

        # 🔹 Calcular cuántos van en cada grupo
        total = len(seguidores)
        por_grupo = total // NUMERO_HILOS  # División entera
        resto = total % NUMERO_HILOS  # Si no es múltiplo de 4, repartimos los sobrantes

        inicio = 0
        for i, clave in enumerate(Division_Seguidores.keys()):
            fin = inicio + por_grupo + (1 if i < resto else 0)
            Division_Seguidores[clave] = seguidores[inicio:fin]
            inicio = fin

        # 🔹 Mostrar el resultado
        for v, lista in Division_Seguidores.items():
            print(f"{v} ({len(lista)} seguidores):")
            for nombre in lista:
                print(f"  → {nombre}")

        print("\n✅ Seguidores divididos correctamente.")

        return True

    except Exception as e:
        print("Error al extraer:", e)
        return []

# =====================================================
# ⚙️ PASO 7: PROCESAMIENTO DE CADA GRUPO EN HILOS
# =====================================================

def procesar_grupo(nombre_grupo, lista_usuarios):
    driver = crear_navegador()
    print(f"🪟 {nombre_grupo} iniciado con {len(lista_usuarios)} usuarios")

    # 🔹 Cargar cookies antes de comenzar
    if not cargar_cookies(driver):
        print(f"⚠️ No se pudieron cargar cookies en {nombre_grupo}, requiere login manual.")
        driver.get("https://www.instagram.com/")
        input("Inicia sesión manualmente y presiona Enter para continuar...")

    cont = 0
    intentos = 0
    total = len(lista_usuarios)

    while cont < total:

        user = lista_usuarios[cont]

        try:
            url = f"https://www.instagram.com/{user}/"
            driver.get(url)

            try:

                # Esperar el elemento que contiene el texto 'seguidores'
                seguidores_elemento = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'seguidores')]"))
                )

                # Extraer el número
                numero_seguidores = seguidores_elemento.find_element(By.XPATH, ".//span[@title]").get_attribute("title")


                # 🔒 Guardar sin conflictos entre hilos
                with lock:
                    Lista_Seguidores_Cantidad[user] = numero_seguidores

                print(f"{nombre_grupo} → {user}: {numero_seguidores} seguidores ({cont}/{total})")

                cont = cont + 1

            except Exception as e:

                if(intentos >= 4):
                    cont = cont + 1
                    intentos = 0

                print(f"❌ Error en {nombre_grupo} con {user}")
                intentos = intentos + 1

        except Exception as e:
            print(f"❌ Error en {nombre_grupo} con {user}")

    print(f"✅ {nombre_grupo} completado")
    driver.quit()

# =====================================================
# 🧵 PASO 8: INICIO Y SINCRONIZACIÓN DE HILOS
# =====================================================

def iniciar_procesos(Division_Seguidores):
    hilos = []
    for grupo, usuarios in Division_Seguidores.items():
        t = threading.Thread(target=procesar_grupo, args=(grupo, usuarios))
        t.start()
        hilos.append(t)
        time.sleep(10)  # pequeño delay para evitar abrir todos al mismo tiempo

    # Esperar a que terminen
    for t in hilos:
        t.join()

        # 🔹 Al terminar todos los hilos
    print("\n🚀 TODOS LOS PROCESOS HAN TERMINADO.\n")
    print(f"Total de usuarios procesados: {len(Lista_Seguidores_Cantidad)}")
    return True

# =====================================================
# 📊 PASO 9: GUARDADO EN EXCEL Y APLICACIÓN DE LA LEY DE BENFORD
# =====================================================

def Guardado_Benford():
    # 🔹 Mostrar resultados finales ordenados
    print("\n📊 Resultados finales:")
    print("-" * 40)
    for usuario, cantidad in Lista_Seguidores_Cantidad.items():
        print(f"→ {usuario}: {cantidad} seguidores")

    # 🔹 Guardar en Excel
    df = pd.DataFrame(list(Lista_Seguidores_Cantidad.items()), columns=['Usuario', 'Seguidores'])
    df.sort_values(by='Seguidores', ascending=False, inplace=True)
    df.to_excel("seguidores_resultado.xlsx", index=False)
    print("\n💾 Resultados guardados en 'seguidores_resultado.xlsx'")

    # 🔹 Aplicar Ley de Benford (primer dígito)
    primeros_digitos = [int(str(valor)[0]) for valor in df['Seguidores'] if str(valor).isdigit()]
    conteo = Counter(primeros_digitos)
    total = sum(conteo.values())

    # 🔹 Calcular porcentajes reales
    porcentajes_reales = {d: (conteo.get(d, 0) / total) * 100 for d in range(1, 10)}

    # 🔹 Porcentajes esperados según la Ley de Benford
    porcentajes_benford = {d: (math.log10(1 + 1/d)) * 100 for d in range(1, 10)}

    # 🔹 Gráfico comparativo
    plt.figure(figsize=(10, 6))
    plt.bar(porcentajes_benford.keys(), porcentajes_benford.values(), alpha=0.6, label="Ley de Benford", color='gray')
    plt.bar(porcentajes_reales.keys(), porcentajes_reales.values(), alpha=0.7, label="Datos Reales", color='skyblue')

    plt.title("Distribución de los primeros dígitos - Ley de Benford")
    plt.xlabel("Primer dígito")
    plt.ylabel("Frecuencia (%)")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.show()


# === EJECUCIÓN ===
if __name__ == "__main__":
    driver = crear_navegador()
    try:
        # Intentar restaurar sesión desde cookies
        if not cargar_cookies(driver):
            # Si no hay cookies, hacer login normal y guardar
            login(driver)

        if abrir_seguidores(driver):
            if hacer_scroll_y_extraer(driver):
                if extraer_visibles(driver):
                    if iniciar_procesos(Division_Seguidores):
                        Guardado_Benford()


    finally:
        input("\nPresiona Enter para cerrar...")
        driver.quit()
