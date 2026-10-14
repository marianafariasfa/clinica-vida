
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "chave-secreta-clinica-2026"

BANCO = "clinica.db"




def conectar():
    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn




def inicializar_banco():
    with conectar() as conn:
        # Tabela de médicos
        conn.execute("""
            CREATE TABLE IF NOT EXISTS medico (
                id_medico INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                crm TEXT NOT NULL UNIQUE,
                especialidade TEXT NOT NULL,
                telefone TEXT
            )
        """)

        # Tabela de usuários
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuario (
                id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL,
                tipo_usuario TEXT NOT NULL DEFAULT 'paciente'
            )
        """)

        # Criar administrador padrão
        usuario = conn.execute(
            "SELECT id_usuario FROM usuario WHERE email = ?",
            ("admin@clinica.com",)
        ).fetchone()

        if usuario is None:
            conn.execute("""
                INSERT INTO usuario (nome, email, senha, tipo_usuario)
                VALUES (?, ?, ?, ?)
            """, (
                "Administrador",
                "admin@clinica.com",
                generate_password_hash("123456"),
                "admin"
            ))

        #Tabela de paciente
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paciente (
                id_paciente INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cpf TEXT NOT NULL UNIQUE,
                data_nascimento TEXT NOT NULL,
                telefone TEXT,
                endereco TEXT
            )
        """)

        #Tabela de agendamentos
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agendamento (
                id_agendamento INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                medico_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                horario TEXT NOT NULL,
                descricao TEXT,
                FOREIGN KEY (paciente_id) REFERENCES paciente(id_paciente),
                FOREIGN KEY (medico_id) REFERENCES medico(id_medico),
                UNIQUE (medico_id, data, horario)
            )
        """)



def login_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper




@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")

        with conectar() as conn:
            usuario = conn.execute(
                "SELECT * FROM usuario WHERE email = ?",
                (email,)
            ).fetchone()

        if usuario and check_password_hash(usuario["senha"], senha):
            session["usuario_id"] = usuario["id_usuario"]
            session["usuario_nome"] = usuario["nome"]
            return redirect(url_for("painel"))

        flash("E-mail ou senha inválidos.", "erro")

    return render_template("login.html")




@app.route("/painel")
@login_obrigatorio
def painel():
    return render_template("painel.html")




@app.route("/usuarios", methods=["GET", "POST"])
@login_obrigatorio
def usuarios():
    with conectar() as conn:
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip()
            senha = request.form.get("senha", "")

            if not nome or not email or not senha:
                flash("Preencha todos os campos.", "erro")
            else:
                try:
                    conn.execute("""
                        INSERT INTO usuario (nome, email, senha)
                        VALUES (?, ?, ?)
                    """, (
                        nome,
                        email,
                        generate_password_hash(senha)
                    ))
                    conn.commit()
                    flash("Usuário cadastrado com sucesso.", "sucesso")
                    return redirect(url_for("usuarios"))

                except sqlite3.IntegrityError:
                    flash("Este e-mail já está cadastrado.", "erro")

        lista = conn.execute("""
            SELECT id_usuario, nome, email, tipo_usuario
            FROM usuario
            ORDER BY nome
        """).fetchall()

    return render_template(
        "usuarios.html",
        usuarios=lista,
        editando=False
    )




@app.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_usuario(id):
    with conectar() as conn:
        usuario = conn.execute(
            "SELECT * FROM usuario WHERE id_usuario = ?",
            (id,)
        ).fetchone()

        if usuario is None:
            flash("Usuário não encontrado.", "erro")
            return redirect(url_for("usuarios"))

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip()
            senha = request.form.get("senha", "")

            if not nome or not email:
                flash("Nome e e-mail são obrigatórios.", "erro")
            else:
                try:
                    if senha:
                        conn.execute("""
                            UPDATE usuario
                            SET nome = ?, email = ?, senha = ?
                            WHERE id_usuario = ?
                        """, (
                            nome,
                            email,
                            generate_password_hash(senha),
                            id
                        ))
                    else:
                        conn.execute("""
                            UPDATE usuario
                            SET nome = ?, email = ?
                            WHERE id_usuario = ?
                        """, (nome, email, id))

                    conn.commit()
                    flash("Usuário atualizado com sucesso.", "sucesso")
                    return redirect(url_for("usuarios"))

                except sqlite3.IntegrityError:
                    flash("Este e-mail já está em uso.", "erro")

        lista = conn.execute("""
            SELECT id_usuario, nome, email, tipo_usuario
            FROM usuario
            ORDER BY nome
        """).fetchall()

    return render_template(
        "usuarios.html",
        usuarios=lista,
        editando=True,
        usuario_edicao=usuario
    )




@app.route("/usuarios/excluir/<int:id>", methods=["POST"])
@login_obrigatorio
def excluir_usuario(id):
    if id == session["usuario_id"]:
        flash("Você não pode excluir sua própria conta.", "erro")
        return redirect(url_for("usuarios"))

    with conectar() as conn:
        conn.execute(
            "DELETE FROM usuario WHERE id_usuario = ?",
            (id,)
        )
        conn.commit()

    flash("Usuário excluído com sucesso.", "sucesso")
    return redirect(url_for("usuarios"))




@app.route("/medicos", methods=["GET", "POST"])
@login_obrigatorio
def medicos():
    with conectar() as conn:
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            crm = request.form.get("crm", "").strip()
            especialidade = request.form.get(
                "especialidade", ""
            ).strip()
            telefone = request.form.get("telefone", "").strip()

            if not nome or not crm or not especialidade:
                flash(
                    "Preencha Nome, CRM e Especialidade.",
                    "erro"
                )
            else:
                try:
                    conn.execute("""
                        INSERT INTO medico
                        (nome, crm, especialidade, telefone)
                        VALUES (?, ?, ?, ?)
                    """, (nome, crm, especialidade, telefone))

                    conn.commit()
                    flash("Médico cadastrado com sucesso.", "sucesso")
                    return redirect(url_for("medicos"))

                except sqlite3.IntegrityError:
                    flash(
                        "Já existe um médico cadastrado com esse CRM.",
                        "erro"
                    )

        lista = conn.execute("""
            SELECT * FROM medico
            ORDER BY nome
        """).fetchall()

    return render_template(
        "medicos.html",
        medicos=lista,
        medico_edicao=None
    )




@app.route("/medicos/editar/<int:id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_medico(id):
    with conectar() as conn:
        medico = conn.execute(
            "SELECT * FROM medico WHERE id_medico = ?",
            (id,)
        ).fetchone()

        if medico is None:
            flash("Médico não encontrado.", "erro")
            return redirect(url_for("medicos"))

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            crm = request.form.get("crm", "").strip()
            especialidade = request.form.get(
                "especialidade", ""
            ).strip()
            telefone = request.form.get("telefone", "").strip()

            if not nome or not crm or not especialidade:
                flash(
                    "Preencha Nome, CRM e Especialidade.",
                    "erro"
                )
            else:
                try:
                    conn.execute("""
                        UPDATE medico
                        SET nome = ?, crm = ?, especialidade = ?,
                            telefone = ?
                        WHERE id_medico = ?
                    """, (
                        nome,
                        crm,
                        especialidade,
                        telefone,
                        id
                    ))

                    conn.commit()
                    flash("Médico atualizado com sucesso.", "sucesso")
                    return redirect(url_for("medicos"))

                except sqlite3.IntegrityError:
                    flash(
                        "Já existe outro médico com esse CRM.",
                        "erro"
                    )

        lista = conn.execute("""
            SELECT * FROM medico
            ORDER BY nome
        """).fetchall()

    return render_template(
        "medicos.html",
        medicos=lista,
        medico_edicao=medico
    )




@app.route("/medicos/excluir/<int:id>", methods=["POST"])
@login_obrigatorio
def excluir_medico(id):
    with conectar() as conn:
        conn.execute(
            "DELETE FROM medico WHERE id_medico = ?",
            (id,)
        )
        conn.commit()

    flash("Médico excluído com sucesso.", "sucesso")
    return redirect(url_for("medicos"))




@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))




@app.route("/pacientes", methods=["GET", "POST"])
@login_obrigatorio
def pacientes():
    with conectar() as conn:
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            cpf = request.form.get("cpf", "").strip()
            data_nascimento = request.form.get("data_nascimento", "").strip()
            telefone = request.form.get("telefone", "").strip()
            endereco = request.form.get("endereco", "").strip()

            if not nome or not cpf or not data_nascimento:
                flash("Preencha Nome, CPF e Data de Nascimento.", "erro")
            else:
                try:
                    conn.execute("""
                        INSERT INTO paciente
                        (nome, cpf, data_nascimento, telefone, endereco)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nome, cpf, data_nascimento, telefone, endereco))
                    conn.commit()
                    flash("Paciente cadastrado com sucesso.", "sucesso")
                    return redirect(url_for("pacientes"))
                except sqlite3.IntegrityError:
                    flash("Já existe um paciente cadastrado com esse CPF.", "erro")

        lista = conn.execute(
            "SELECT * FROM paciente ORDER BY nome"
        ).fetchall()

    return render_template(
        "pacientes.html", pacientes=lista, paciente_edicao=None
    )


@app.route("/pacientes/editar/<int:id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_paciente(id):
    with conectar() as conn:
        paciente = conn.execute(
            "SELECT * FROM paciente WHERE id_paciente = ?", (id,)
        ).fetchone()

        if paciente is None:
            flash("Paciente não encontrado.", "erro")
            return redirect(url_for("pacientes"))

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            cpf = request.form.get("cpf", "").strip()
            data_nascimento = request.form.get("data_nascimento", "").strip()
            telefone = request.form.get("telefone", "").strip()
            endereco = request.form.get("endereco", "").strip()

            if not nome or not cpf or not data_nascimento:
                flash("Preencha Nome, CPF e Data de Nascimento.", "erro")
            else:
                try:
                    conn.execute("""
                        UPDATE paciente
                        SET nome = ?, cpf = ?, data_nascimento = ?,
                            telefone = ?, endereco = ?
                        WHERE id_paciente = ?
                    """, (nome, cpf, data_nascimento, telefone, endereco, id))
                    conn.commit()
                    flash("Paciente atualizado com sucesso.", "sucesso")
                    return redirect(url_for("pacientes"))
                except sqlite3.IntegrityError:
                    flash("Já existe outro paciente cadastrado com esse CPF.", "erro")

        lista = conn.execute(
            "SELECT * FROM paciente ORDER BY nome"
        ).fetchall()

    return render_template(
        "pacientes.html", pacientes=lista, paciente_edicao=paciente
    )


@app.route("/pacientes/excluir/<int:id>", methods=["POST"])
@login_obrigatorio
def excluir_paciente(id):
    with conectar() as conn:
        conn.execute(
            "DELETE FROM paciente WHERE id_paciente = ?", (id,)
        )
        conn.commit()

    flash("Paciente excluído com sucesso.", "sucesso")
    return redirect(url_for("pacientes"))



def carregar_agendamentos(conn):
    return conn.execute("""
        SELECT a.*, p.nome AS paciente_nome, m.nome AS medico_nome
        FROM agendamento a
        JOIN paciente p ON p.id_paciente = a.paciente_id
        JOIN medico m ON m.id_medico = a.medico_id
        ORDER BY a.data, a.horario, m.nome
    """).fetchall()


@app.route("/agendamentos", methods=["GET", "POST"])
@login_obrigatorio
def agendamentos():
    with conectar() as conn:
        if request.method == "POST":
            paciente_id = request.form.get("paciente_id", type=int)
            medico_id = request.form.get("medico_id", type=int)
            data = request.form.get("data", "").strip()
            horario = request.form.get("horario", "").strip()
            descricao = request.form.get("descricao", "").strip()

            if not paciente_id or not medico_id or not data or not horario:
                flash("Preencha Paciente, Médico, Data e Horário.", "erro")
            else:
                try:
                    conn.execute("""
                        INSERT INTO agendamento
                        (paciente_id, medico_id, data, horario, descricao)
                        VALUES (?, ?, ?, ?, ?)
                    """, (paciente_id, medico_id, data, horario, descricao))
                    conn.commit()
                    flash("Agendamento realizado com sucesso.", "sucesso")
                    return redirect(url_for("agendamentos"))
                except sqlite3.IntegrityError as erro:
                    if "UNIQUE constraint failed" in str(erro):
                        flash("Este médico já possui uma consulta nessa data e horário. Escolha outro horário.", "erro")
                    else:
                        flash("Não foi possível salvar. Confira se o paciente e o médico existem.", "erro")

        lista_pacientes = conn.execute(
            "SELECT id_paciente, nome, cpf FROM paciente ORDER BY nome"
        ).fetchall()
        lista_medicos = conn.execute(
            "SELECT id_medico, nome, especialidade FROM medico ORDER BY nome"
        ).fetchall()
        lista_agendamentos = carregar_agendamentos(conn)

    return render_template(
        "agendamentos.html", pacientes=lista_pacientes,
        medicos=lista_medicos, agendamentos=lista_agendamentos,
        agendamento_edicao=None
    )


@app.route("/agendamentos/editar/<int:id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_agendamento(id):
    with conectar() as conn:
        atual = conn.execute(
            "SELECT * FROM agendamento WHERE id_agendamento = ?", (id,)
        ).fetchone()
        if atual is None:
            flash("Agendamento não encontrado.", "erro")
            return redirect(url_for("agendamentos"))

        if request.method == "POST":
            paciente_id = request.form.get("paciente_id", type=int)
            medico_id = request.form.get("medico_id", type=int)
            data = request.form.get("data", "").strip()
            horario = request.form.get("horario", "").strip()
            descricao = request.form.get("descricao", "").strip()

            if not paciente_id or not medico_id or not data or not horario:
                flash("Preencha Paciente, Médico, Data e Horário.", "erro")
            else:
                try:
                    conn.execute("""
                        UPDATE agendamento
                        SET paciente_id = ?, medico_id = ?, data = ?,
                            horario = ?, descricao = ?
                        WHERE id_agendamento = ?
                    """, (paciente_id, medico_id, data, horario, descricao, id))
                    conn.commit()
                    flash("Agendamento atualizado com sucesso.", "sucesso")
                    return redirect(url_for("agendamentos"))
                except sqlite3.IntegrityError as erro:
                    if "UNIQUE constraint failed" in str(erro):
                        flash("Este médico já possui outra consulta nessa data e horário.", "erro")
                    else:
                        flash("Não foi possível atualizar. Confira paciente e médico.", "erro")

        # Recarrega os dados atuais para preencher o formulário
        atual = conn.execute(
            "SELECT * FROM agendamento WHERE id_agendamento = ?", (id,)
        ).fetchone()
        lista_pacientes = conn.execute(
            "SELECT id_paciente, nome, cpf FROM paciente ORDER BY nome"
        ).fetchall()
        lista_medicos = conn.execute(
            "SELECT id_medico, nome, especialidade FROM medico ORDER BY nome"
        ).fetchall()
        lista_agendamentos = carregar_agendamentos(conn)

    return render_template(
        "agendamentos.html", pacientes=lista_pacientes,
        medicos=lista_medicos, agendamentos=lista_agendamentos,
        agendamento_edicao=atual
    )


@app.route("/agendamentos/cancelar/<int:id>", methods=["POST"])
@login_obrigatorio
def cancelar_agendamento(id):
    with conectar() as conn:
        cursor = conn.execute(
            "DELETE FROM agendamento WHERE id_agendamento = ?", (id,)
        )
        conn.commit()
    if cursor.rowcount:
        flash("Agendamento cancelado com sucesso.", "sucesso")
    else:
        flash("Agendamento não encontrado.", "erro")
    return redirect(url_for("agendamentos"))



if __name__ == "__main__":
    inicializar_banco()
    app.run(debug=True)
