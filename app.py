import base64
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash, make_response, send_from_directory
from flask_weasyprint import HTML
import sqlite3
import os
import uuid
from datetime import datetime
from PIL import Image

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
DB = "relatorios.db"
UPLOAD_FOLDER = "uploads"

# Criar pasta de uploads se não existir
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ----------------- BANCO -----------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Tabela principal
    c.execute('''
        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_rev TEXT,
            num_os TEXT,
            cliente TEXT,
            data TEXT,
            tecnico TEXT,
            nivel TEXT,
            contato TEXT,
            modelo TEXT,
            prefixo TEXT,
            serie TEXT,
            instrucoes TEXT,
            reclamacao TEXT,
            causa TEXT,
            dano TEXT,
            comentarios TEXT,
            peca_numero TEXT,
            falha_codigo TEXT,
            falha_qtd TEXT,
            smcs_code TEXT,
            grupo_part TEXT,
            comentarios_adicionais TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabela de fotos
    c.execute('''
        CREATE TABLE IF NOT EXISTS fotos_relatorio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            relatorio_id INTEGER,
            nome_arquivo TEXT,
            caminho_arquivo TEXT,
            titulo TEXT,
            FOREIGN KEY (relatorio_id) REFERENCES relatorios (id)
        )
    ''')

    conn.commit()
    conn.close()


def buscar_fotos_seguro(relatorio_id):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='fotos_relatorio'
        """)
        if cursor.fetchone():
            cursor.execute('SELECT * FROM fotos_relatorio WHERE relatorio_id = ?', (relatorio_id,))
            fotos_raw = cursor.fetchall()
            
            fotos = []
            for foto in fotos_raw:
                arquivo_path = os.path.join(UPLOAD_FOLDER, foto[2])
                if os.path.exists(arquivo_path):
                    fotos.append(foto)
            return fotos
        else:
            return []
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# ----------------- ROTAS -----------------
@app.route("/")
def index():
    return render_template("form.html", editando=False)


@app.route("/salvar", methods=["POST"])
def salvar():
    dados = tuple(request.form.get(x) for x in [
        "cod_rev", "num_os", "cliente", "data", "tecnico", "nivel", "contato",
        "modelo", "prefixo", "serie", "instrucoes", "reclamacao", "causa",
        "dano", "comentarios", "peca_numero", "falha_codigo", "falha_qtd",
        "smcs_code", "grupo_part", "comentarios_adicionais"
    ])

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO relatorios 
        (cod_rev, num_os, cliente, data, tecnico, nivel, contato, modelo, prefixo, serie,
         instrucoes, reclamacao, causa, dano, comentarios,
         peca_numero, falha_codigo, falha_qtd, smcs_code, grupo_part, comentarios_adicionais)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, dados)
    relatorio_id = c.lastrowid

    # Salvar fotos enviadas no mesmo formulário
    if "fotos" in request.files:
        arquivos = request.files.getlist("fotos")
        nomes_fotos = request.form.getlist("foto_nomes[]")  # nomes vindos do form

        for idx, foto in enumerate(arquivos):
            if foto.filename:
                titulo = nomes_fotos[idx] if idx < len(nomes_fotos) else "Sem nome"

                filename = str(uuid.uuid4()) + os.path.splitext(foto.filename)[1].lower()
                filepath = os.path.join(UPLOAD_FOLDER, filename)

                os.makedirs(UPLOAD_FOLDER, exist_ok=True)

                img = Image.open(foto)
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

                img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                img.save(filepath, quality=85, optimize=True)

                # Agora salva também o título (nome dado pelo usuário)
                c.execute("""
                    INSERT INTO fotos_relatorio (relatorio_id, nome_arquivo, caminho_arquivo, titulo)
                    VALUES (?, ?, ?, ?)
                """, (relatorio_id, filename, filename, titulo))

    conn.commit()
    conn.close()

    flash("Relatório e fotos salvos com sucesso!", "success")
    return redirect(url_for("ver", relatorio_id=relatorio_id))

@app.route("/listar")
def listar():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        SELECT 
            id,           -- r[0]
            cod_rev,      -- r[1]
            num_os,       -- r[2]
            cliente,      -- r[3]
            data,         -- r[4]
            tecnico,      -- r[5]
            nivel,        -- r[6]
            contato,      -- r[7]
            modelo,       -- r[8]
            serie,        -- r[9]
            created_at    -- r[10]
        FROM relatorios
        ORDER BY created_at DESC
    """)
    relatorios = c.fetchall()
    conn.close()
    return render_template("listar.html", relatorios=relatorios)

@app.route("/ver/<int:relatorio_id>")
def ver(relatorio_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM relatorios WHERE id=?", (relatorio_id,))
    relatorio = c.fetchone()
    conn.close()
    
    if not relatorio:
        flash("Relatório não encontrado!", "error")
        return redirect(url_for("listar"))
    
    fotos = buscar_fotos_seguro(relatorio_id)
    return render_template("ver.html", relatorio=relatorio, fotos=fotos)


@app.route("/upload_foto/<int:relatorio_id>", methods=["POST"])
def upload_foto(relatorio_id):
    print(f"Upload solicitado para relatório ID: {relatorio_id}")
    
    if 'foto' not in request.files:
        print("Erro: Nenhuma foto enviada")
        return jsonify({'error': 'Nenhuma foto enviada'}), 400

    foto = request.files['foto']
    if foto.filename == '':
        print("Erro: Nenhuma foto selecionada")
        return jsonify({'error': 'Nenhuma foto selecionada'}), 400

    # Verificar se é uma imagem
    if not foto.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        print("Erro: Formato de arquivo não suportado")
        return jsonify({'error': 'Formato de arquivo não suportado'}), 400

    try:
        # Gerar nome único apenas com extensão
        filename = str(uuid.uuid4()) + os.path.splitext(foto.filename)[1].lower()
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        print(f"Salvando arquivo: {filename} em {filepath}")

        # Criar diretório se não existir
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Processar e salvar a imagem
        img = Image.open(foto)
        # Converter RGBA para RGB se necessário
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        img.thumbnail((800, 600), Image.Resampling.LANCZOS)
        img.save(filepath, quality=85, optimize=True)
        
        print(f"Arquivo salvo com sucesso: {filepath}")
        
        # Salvar no banco - CORREÇÃO: salvar apenas o filename
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO fotos_relatorio (relatorio_id, nome_arquivo, caminho_arquivo) VALUES (?, ?, ?)",
                  (relatorio_id, filename, filename))  # Ambos filename
        conn.commit()
        conn.close()
        
        print(f"Registro inserido no banco para arquivo: {filename}")
        
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        print(f"Erro ao salvar foto: {str(e)}")
        return jsonify({'error': f'Erro ao processar imagem: {str(e)}'}), 500


@app.route('/uploads/<path:filename>')
def uploads(filename):
    """Serve arquivos da pasta uploads"""
    try:
        print(f"Servindo arquivo: {filename}")
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception as e:
        print(f"Erro ao servir arquivo {filename}: {e}")
        return "Arquivo não encontrado", 404


@app.route('/pdf/<int:relatorio_id>')
def gerar_pdf(relatorio_id):
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM relatorios WHERE id = ?', (relatorio_id,))
        relatorio = cursor.fetchone()
        conn.close()

        if not relatorio:
            return "Relatório não encontrado", 404

        fotos = buscar_fotos_seguro(relatorio_id)

        html = render_template('pdf_template.html',
                               relatorio=relatorio,
                               fotos=fotos)

        pdf = HTML(string=html, base_url=request.base_url).write_pdf()

        num_os = relatorio[2] or f"OS_{relatorio_id}"
        num_os_safe = "".join(c if c.isalnum() else "_" for c in num_os)

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=relatorio_{num_os_safe}.pdf'

        return response
    except Exception as e:
        return f"Erro ao gerar PDF: {str(e)}", 500


@app.route('/pdf/visualizar/<int:relatorio_id>')
def visualizar_pdf(relatorio_id):
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM relatorios WHERE id = ?', (relatorio_id,))
        relatorio = cursor.fetchone()
        conn.close()

        if not relatorio:
            return "Relatório não encontrado", 404

        fotos = buscar_fotos_seguro(relatorio_id)

        html = render_template('pdf_template.html',
                               relatorio=relatorio,
                               fotos=fotos)

        pdf = HTML(string=html, base_url=request.base_url).write_pdf()

        # usa número da OS como nome do arquivo
        num_os = relatorio[2] or f"OS_{relatorio_id}"
        num_os_safe = "".join(c if c.isalnum() else "_" for c in num_os)

        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=relatorio_{num_os_safe}.pdf'

        return response
    except Exception as e:
        print(f"Erro ao visualizar PDF: {str(e)}")
        return f"Erro ao visualizar PDF: {str(e)}", 500


@app.route("/debug_fotos/<int:relatorio_id>")
def debug_fotos(relatorio_id):
    """Função para debugar problemas com fotos"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Verificar se a tabela existe
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fotos_relatorio'")
    tabela_existe = c.fetchone()
    
    if not tabela_existe:
        return "Tabela fotos_relatorio não existe!"
    
    # Buscar fotos
    c.execute('SELECT * FROM fotos_relatorio WHERE relatorio_id = ?', (relatorio_id,))
    fotos = c.fetchall()
    conn.close()
    
    # Verificar arquivos no disco
    uploads_dir = UPLOAD_FOLDER
    arquivos_disco = []
    if os.path.exists(uploads_dir):
        arquivos_disco = os.listdir(uploads_dir)
    
    debug_info = f"""
    <h2>Debug - Relatório {relatorio_id}</h2>
    <p><strong>Upload Folder:</strong> {UPLOAD_FOLDER}</p>
    <p><strong>Upload Folder Exists:</strong> {os.path.exists(UPLOAD_FOLDER)}</p>
    <p><strong>Tabela Existe:</strong> {bool(tabela_existe)}</p>
    
    <h3>Fotos no Banco ({len(fotos)}):</h3>
    <ul>
    """
    
    for foto in fotos:
        debug_info += f"<li>ID: {foto[0]}, Nome: {foto[2]}, Arquivo existe: {os.path.exists(os.path.join(UPLOAD_FOLDER, foto[2]))}</li>"
    
    debug_info += f"""
    </ul>
    
    <h3>Arquivos no Disco ({len(arquivos_disco)}):</h3>
    <ul>
    """
    
    for arquivo in arquivos_disco:
        debug_info += f"<li>{arquivo}</li>"
    
    debug_info += """
    </ul>
    
    <h3>Teste de Imagens:</h3>
    """
    
    for foto in fotos:
        debug_info += f'<img src="/uploads/{foto[2]}" alt="Foto" style="max-width:200px; margin:10px; border:1px solid #ccc;"><br>'
    
    return debug_info



# ----------------- ROTA PARA DELETAR FOTO (BONUS) -----------------
@app.route("/deletar_foto/<int:foto_id>", methods=["POST"])
def deletar_foto(foto_id):
    """Deletar foto do banco e do disco"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Buscar arquivo antes de deletar
        c.execute('SELECT caminho_arquivo FROM fotos_relatorio WHERE id = ?', (foto_id,))
        resultado = c.fetchone()
        
        if resultado:
            arquivo = resultado[0]
            
            # Deletar do banco
            c.execute('DELETE FROM fotos_relatorio WHERE id = ?', (foto_id,))
            conn.commit()
            
            # Deletar arquivo do disco
            caminho_arquivo = os.path.join(UPLOAD_FOLDER, arquivo)
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)
                
            conn.close()
            return jsonify({'success': True})
        else:
            conn.close()
            return jsonify({'error': 'Foto não encontrada'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/editar_foto/<int:foto_id>", methods=["POST"])
def editar_foto(foto_id):
    try:
        data = request.get_json()
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "Imagem não enviada"}), 400

        # Buscar foto no banco
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT caminho_arquivo FROM fotos_relatorio WHERE id = ?", (foto_id,))
        resultado = c.fetchone()
        conn.close()

        if not resultado:
            return jsonify({"error": "Foto não encontrada"}), 404

        caminho_arquivo = os.path.join(UPLOAD_FOLDER, resultado[0])

        # Decodificar base64 e salvar
        header, encoded = image_b64.split(",", 1)
        img_data = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_data))
        img.save(caminho_arquivo, quality=85, optimize=True)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/editar/<int:relatorio_id>", methods=["GET", "POST"])
def editar(relatorio_id):
    conn = sqlite3.connect(DB)
    # Usar Row para facilitar o acesso por nome da coluna no template
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()

    if request.method == "POST":
        # 1. ATUALIZAR DADOS DE TEXTO
        dados = {
            "cod_rev": request.form.get("cod_rev"),
            "num_os": request.form.get("num_os"),
            "cliente": request.form.get("cliente"),
            "data": request.form.get("data"),
            "tecnico": request.form.get("tecnico"),
            "nivel": request.form.get("nivel"),
            "contato": request.form.get("contato"),
            "modelo": request.form.get("modelo"),
            "prefixo": request.form.get("prefixo"),
            "serie": request.form.get("serie"),
            "instrucoes": request.form.get("instrucoes"),
            "reclamacao": request.form.get("reclamacao"),
            "causa": request.form.get("causa"),
            "dano": request.form.get("dano"),
            "comentarios": request.form.get("comentarios"),
            "peca_numero": request.form.get("peca_numero"),
            "falha_codigo": request.form.get("falha_codigo"),
            "falha_qtd": request.form.get("falha_qtd"),
            "smcs_code": request.form.get("smcs_code"),
            "grupo_part": request.form.get("grupo_part"),
            "comentarios_adicionais": request.form.get("comentarios_adicionais"),
        }
        
        c.execute("""
            UPDATE relatorios SET
            cod_rev=?, num_os=?, cliente=?, data=?, tecnico=?, nivel=?, contato=?,
            modelo=?, prefixo=?, serie=?, instrucoes=?, reclamacao=?, causa=?,
            dano=?, comentarios=?, peca_numero=?, falha_codigo=?, falha_qtd=?,
            smcs_code=?, grupo_part=?, comentarios_adicionais=?
            WHERE id=?
        """, (*dados.values(), relatorio_id))

        # 2. REMOVER FOTOS MARCADAS
        fotos_para_remover = request.form.getlist("remover_foto")
        if fotos_para_remover:
            for foto_id in fotos_para_remover:
                # Buscar o nome do arquivo para deletar do disco
                c.execute("SELECT caminho_arquivo FROM fotos_relatorio WHERE id=?", (foto_id,))
                resultado = c.fetchone()
                if resultado:
                    caminho_arquivo = os.path.join(UPLOAD_FOLDER, resultado['caminho_arquivo'])
                    if os.path.exists(caminho_arquivo):
                        os.remove(caminho_arquivo)
                
                # Deletar do banco de dados
                c.execute("DELETE FROM fotos_relatorio WHERE id=?", (foto_id,))

        # 3. ADICIONAR NOVAS FOTOS (lógica similar à de 'salvar')
        if "fotos" in request.files:
            arquivos = request.files.getlist("fotos")
            nomes_fotos = request.form.getlist("foto_nomes[]")

            for idx, foto in enumerate(arquivos):
                if foto.filename:
                    titulo = nomes_fotos[idx] if idx < len(nomes_fotos) else "Sem título"
                    filename = str(uuid.uuid4()) + os.path.splitext(foto.filename)[1].lower()
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    
                    img = Image.open(foto)
                    if img.mode in ('RGBA', 'LA'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    
                    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                    img.save(filepath, quality=85, optimize=True)
                    
                    c.execute("""
                        INSERT INTO fotos_relatorio (relatorio_id, nome_arquivo, caminho_arquivo, titulo)
                        VALUES (?, ?, ?, ?)
                    """, (relatorio_id, filename, filename, titulo))

        conn.commit()
        conn.close()
        flash("Relatório atualizado com sucesso!", "success")
        return redirect(url_for("ver", relatorio_id=relatorio_id))

    # --- Lógica para o método GET (carregar o formulário) ---
    c.execute("SELECT * FROM relatorios WHERE id=?", (relatorio_id,))
    relatorio = c.fetchone()
    
    if not relatorio:
        conn.close()
        flash("Relatório não encontrado!", "error")
        return redirect(url_for("listar"))

    fotos = buscar_fotos_seguro(relatorio_id)
    conn.close()
    
    # Renderiza um novo template 'editar.html'
    return render_template("editar.html", relatorio=relatorio, fotos=fotos)
    
if __name__ == "__main__":
    init_db()
    app.run(debug=True)