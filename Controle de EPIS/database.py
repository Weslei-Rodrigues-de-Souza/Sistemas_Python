import sqlite3
import datetime
import os
from decimal import Decimal, ROUND_HALF_UP

DB_NAME = "sales_system.db"

class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name

    def _get_connection(self):
        """Estabelece e retorna uma conexão com o banco de dados."""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row # Permite acessar colunas por nome
        return conn

    def execute_query(self, query, params=(), fetch_one=False, fetch_all=False, commit=True):
        """
        Executa uma consulta SQL.
        Gerencia a criação e o fechamento da conexão e do cursor.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            last_row_id = cursor.lastrowid # Captura o ID da última linha inserida

            if commit: # Realiza o commit se a operação modificar dados e commit=True
                conn.commit()

            if fetch_one: # Retorna uma única linha
                return cursor.fetchone()
            if fetch_all: # Retorna todas as linhas
                return cursor.fetchall()
            if last_row_id: # Retorna o ID da última linha inserida (para INSERTs)
                return last_row_id
            # Para UPDATE/DELETE, retorna o número de linhas afetadas se não for fetch_one/all ou last_row_id
            return cursor.rowcount if not (fetch_one or fetch_all or last_row_id) else None
        except sqlite3.Error as e:
            print(f"Database error: {e} with query: {query} and params: {params}")
            if conn: # Desfaz a transação em caso de erro
                conn.rollback()
            # Para operações de modificação, é importante propagar o erro.
            # Para SELECTs, um erro pode significar que a tabela não existe ou outro problema.
            if not (fetch_one or fetch_all):
                raise e # Propaga a exceção para ser tratada pela camada da aplicação
            return None if fetch_one else [] if fetch_all else None # Para SELECTs, retorna indicativo de falha
        finally:
            if conn: # Garante que a conexão seja sempre fechada
                conn.close()

    def add_column_to_table(self, table_name, column_name, column_definition):
        """Adiciona uma coluna a uma tabela se ela não existir."""
        # Check if column exists
        cursor = self._get_connection().cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [column[1] for column in cursor.fetchall()]
        if column_name not in columns:
            self.execute_query(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition};")

    def create_tables(self):
        """Cria todas as tabelas necessárias se elas ainda não existirem."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT,
                telefone TEXT,
                endereco_rua TEXT,
                endereco_numero TEXT,
                endereco_bairro TEXT,
                endereco_cidade TEXT,
                endereco_uf TEXT,
                endereco_cep TEXT,
                data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS grupos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                descricao TEXT,
                data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                grupo_id INTEGER,
                data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (grupo_id) REFERENCES grupos (id) ON DELETE SET NULL,
                UNIQUE (nome, grupo_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                descricao TEXT,
                preco_venda REAL NOT NULL,
                quantidade_estoque INTEGER DEFAULT 0,
                unidade_medida TEXT,
                categoria_id INTEGER,
                data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (categoria_id) REFERENCES categorias (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS produto_imagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                caminho_imagem TEXT NOT NULL,
                legenda TEXT,
                data_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS estoque_entradas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_custo REAL,
                fornecedor TEXT,
                data_entrada DATETIME DEFAULT CURRENT_TIMESTAMP,
                observacao TEXT,
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                data_venda DATETIME DEFAULT CURRENT_TIMESTAMP,
                valor_total REAL NOT NULL,
                status TEXT DEFAULT 'Rascunho',
                observacao TEXT,
                forma_pagamento TEXT,
                numero_parcelas INTEGER DEFAULT 1,
                periodo_pagamento_parcelas TEXT,
                FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS venda_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario_venda REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (venda_id) REFERENCES vendas (id) ON DELETE CASCADE,
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE RESTRICT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS lancamentos_financeiros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER,
                descricao TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('Receita', 'Despesa')),
                valor REAL NOT NULL,
                numero_parcela_atual INTEGER DEFAULT 1,
                total_parcelas INTEGER DEFAULT 1,
                data_vencimento DATE NOT NULL,
                status_pagamento TEXT DEFAULT 'Pendente' CHECK(status_pagamento IN ('Pendente', 'Pago', 'Vencido', 'Cancelado')),
                forma_pagamento_efetiva TEXT,
                observacao TEXT,
                data_lancamento DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_pagamento DATE,
                FOREIGN KEY (venda_id) REFERENCES vendas (id) ON DELETE SET NULL
            )
            """
        ]
        for query_stmt in queries:
            self.execute_query(query_stmt)
        self.add_column_to_table('lancamentos_financeiros', 'numero_parcela_atual', 'INTEGER DEFAULT 1')
        print("Tables checked/created successfully.")

    # --- Imagens de Produto ---
    def add_produto_imagem(self, produto_id, caminho_imagem, legenda=None):
        query = "INSERT INTO produto_imagens (produto_id, caminho_imagem, legenda) VALUES (?, ?, ?)"
        params = (produto_id, caminho_imagem, legenda)
        return self.execute_query(query, params)

    def get_imagens_por_produto_id(self, produto_id):
        query = "SELECT id, caminho_imagem, legenda FROM produto_imagens WHERE produto_id = ? ORDER BY data_upload ASC"
        return self.execute_query(query, (produto_id,), fetch_all=True)

    def delete_produto_imagem(self, imagem_id, app_upload_folder):
        imagem = self.execute_query("SELECT caminho_imagem FROM produto_imagens WHERE id = ?", (imagem_id,), fetch_one=True)
        if imagem and imagem['caminho_imagem']:
            try:
                caminho_completo = os.path.join(app_upload_folder, imagem['caminho_imagem'])
                if os.path.exists(caminho_completo):
                    os.remove(caminho_completo)
            except OSError as e:
                print(f"Erro ao deletar arquivo de imagem {caminho_completo}: {e}")
        deleted_rows = self.execute_query("DELETE FROM produto_imagens WHERE id = ?", (imagem_id,))
        return deleted_rows is not None and deleted_rows > 0

    # --- Grupos ---
    def add_grupo(self, data):
        query = "INSERT INTO grupos (nome, descricao) VALUES (?, ?)"
        params = (data['nome'], data.get('descricao'))
        return self.execute_query(query, params)

    def get_all_grupos(self, search_term=None):
        query_str = "SELECT * FROM grupos"
        params = []
        if search_term:
            query_str += " WHERE nome LIKE ? OR descricao LIKE ?"
            params.extend([f'%{search_term}%', f'%{search_term}%'])
        query_str += " ORDER BY nome ASC"
        return self.execute_query(query_str, params, fetch_all=True)

    def get_grupo_by_id(self, grupo_id):
        query = "SELECT * FROM grupos WHERE id = ?"
        return self.execute_query(query, (grupo_id,), fetch_one=True)

    def update_grupo(self, grupo_id, data):
        query = "UPDATE grupos SET nome = ?, descricao = ? WHERE id = ?"
        params = (data['nome'], data.get('descricao'), grupo_id)
        self.execute_query(query, params)
        return True

    def delete_grupo(self, grupo_id):
        try:
            self.execute_query("DELETE FROM grupos WHERE id = ?", (grupo_id,))
            return True
        except Exception as e:
            print(f"Error deleting grupo {grupo_id}: {e}")
            return False

    # --- Categorias ---
    def add_categoria(self, data):
        query = "INSERT INTO categorias (nome, descricao, grupo_id) VALUES (?, ?, ?)"
        params = (data['nome'], data.get('descricao'), data.get('grupo_id'))
        return self.execute_query(query, params)

    def get_all_categorias(self, search_term=None):
        query_str = "SELECT cat.*, g.nome as grupo_nome FROM categorias cat LEFT JOIN grupos g ON cat.grupo_id = g.id"
        params = []
        if search_term:
            query_str += " WHERE cat.nome LIKE ? OR cat.descricao LIKE ? OR g.nome LIKE ?"
            params.extend([f'%{search_term}%',f'%{search_term}%',f'%{search_term}%'])
        query_str += " ORDER BY g.nome ASC, cat.nome ASC"
        return self.execute_query(query_str, params, fetch_all=True)

    def get_categoria_by_id(self, categoria_id):
        query = "SELECT cat.*, g.nome as grupo_nome FROM categorias cat LEFT JOIN grupos g ON cat.grupo_id = g.id WHERE cat.id = ?"
        return self.execute_query(query, (categoria_id,), fetch_one=True)

    def update_categoria(self, categoria_id, data):
        query = "UPDATE categorias SET nome = ?, descricao = ?, grupo_id = ? WHERE id = ?"
        params = (data['nome'], data.get('descricao'), data.get('grupo_id'), categoria_id)
        self.execute_query(query, params)
        return True

    def delete_categoria(self, categoria_id):
        try:
            self.execute_query("DELETE FROM categorias WHERE id = ?", (categoria_id,))
            return True
        except Exception as e:
            print(f"Error deleting categoria {categoria_id}: {e}")
            return False

    # --- Clientes ---
    def add_cliente(self, data):
        query = "INSERT INTO clientes (nome, email, telefone, endereco_rua, endereco_numero, endereco_bairro, endereco_cidade, endereco_uf, endereco_cep) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        params = (data['nome'], data.get('email'), data.get('telefone'), data.get('endereco_rua'), data.get('endereco_numero'), data.get('endereco_bairro'), data.get('endereco_cidade'), data.get('endereco_uf'), data.get('endereco_cep'))
        return self.execute_query(query, params)

    def get_all_clientes(self, search_term=None):
        query_str = "SELECT * FROM clientes"
        params = []
        if search_term:
            query_str += " WHERE nome LIKE ? OR email LIKE ? OR telefone LIKE ?"
            params.extend([f'%{search_term}%',f'%{search_term}%',f'%{search_term}%'])
        query_str += " ORDER BY nome ASC"
        return self.execute_query(query_str, params, fetch_all=True)

    def get_cliente_by_id(self, cliente_id):
        query = "SELECT * FROM clientes WHERE id = ?"
        return self.execute_query(query, (cliente_id,), fetch_one=True)

    def update_cliente(self, cliente_id, data):
        query = "UPDATE clientes SET nome=?, email=?, telefone=?, endereco_rua=?, endereco_numero=?, endereco_bairro=?, endereco_cidade=?, endereco_uf=?, endereco_cep=? WHERE id = ?"
        params = (data['nome'], data.get('email'), data.get('telefone'), data.get('endereco_rua'), data.get('endereco_numero'), data.get('endereco_bairro'), data.get('endereco_cidade'), data.get('endereco_uf'), data.get('endereco_cep'), cliente_id)
        self.execute_query(query, params)
        return True

    def delete_cliente(self, cliente_id):
        try:
            self.execute_query("DELETE FROM clientes WHERE id = ?", (cliente_id,))
            return True
        except Exception as e:
            print(f"Error deleting cliente {cliente_id}: {e}")
            return False

    # --- Produtos ---
    def add_produto(self, data):
        query = "INSERT INTO produtos (nome, descricao, preco_venda, quantidade_estoque, unidade_medida, categoria_id) VALUES (?, ?, ?, ?, ?, ?)"
        params = (data['nome'], data.get('descricao'), data['preco_venda'], data.get('quantidade_estoque', 0), data.get('unidade_medida'), data.get('categoria_id'))
        return self.execute_query(query, params)

    def get_all_produtos(self, search_term=None):
        query_str = """
        SELECT p.*, cat.nome as categoria_nome, g.nome as grupo_nome,
               (SELECT pi.caminho_imagem FROM produto_imagens pi WHERE pi.produto_id = p.id ORDER BY pi.id ASC LIMIT 1) as imagem_principal
        FROM produtos p
        LEFT JOIN categorias cat ON p.categoria_id = cat.id
        LEFT JOIN grupos g ON cat.grupo_id = g.id
        """
        params = []
        if search_term:
            query_str += " WHERE p.nome LIKE ? OR p.descricao LIKE ? OR cat.nome LIKE ? OR g.nome LIKE ?"
            params.extend([f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'])
        query_str += " ORDER BY p.nome ASC"
        return self.execute_query(query_str, params, fetch_all=True)

    def get_produto_by_id(self, produto_id):
        query_produto = """
        SELECT p.*, cat.nome as categoria_nome, cat.id as categoria_id, g.nome as grupo_nome, g.id as grupo_id
        FROM produtos p
        LEFT JOIN categorias cat ON p.categoria_id = cat.id
        LEFT JOIN grupos g ON cat.grupo_id = g.id
        WHERE p.id = ?
        """
        return self.execute_query(query_produto, (produto_id,), fetch_one=True)

    def update_produto(self, produto_id, data):
        query = "UPDATE produtos SET nome=?, descricao=?, preco_venda=?, quantidade_estoque=?, unidade_medida=?, categoria_id=? WHERE id = ?"
        params = (data['nome'], data.get('descricao'), data['preco_venda'], data.get('quantidade_estoque', 0), data.get('unidade_medida'), data.get('categoria_id'), produto_id)
        self.execute_query(query, params)
        return True

    def delete_produto(self, produto_id, app_upload_folder):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            imagens = self.get_imagens_por_produto_id(produto_id)
            for img in imagens:
                if img and img['caminho_imagem']:
                    caminho_completo = os.path.join(app_upload_folder, img['caminho_imagem'])
                    if os.path.exists(caminho_completo):
                        try:
                            os.remove(caminho_completo)
                        except OSError as e:
                            print(f"Erro ao deletar arquivo de imagem {caminho_completo} para produto {produto_id}: {e}")
            cursor.execute("DELETE FROM produto_imagens WHERE produto_id = ?", (produto_id,))
            cursor.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
            conn.commit()
            return True
        except sqlite3.IntegrityError as e:
            print(f"Erro de integridade ao deletar produto {produto_id}: {e}. Pode estar em uma venda.")
            if conn: conn.rollback()
            return False
        except Exception as e:
            print(f"Erro ao deletar produto {produto_id}: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()

    def update_estoque_produto(self, produto_id, quantidade_alterada, is_venda=True, conn=None):
        op = "-" if is_venda else "+"
        query = f"UPDATE produtos SET quantidade_estoque = quantidade_estoque {op} ? WHERE id = ?"
        use_external_conn = conn is not None
        current_conn = conn if use_external_conn else self._get_connection()
        cursor = current_conn.cursor()
        try:
            cursor.execute(query, (quantidade_alterada, produto_id))
            if not use_external_conn: current_conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating stock for product {produto_id}: {e}")
            if not use_external_conn and current_conn: current_conn.rollback()
            raise
        finally:
            if not use_external_conn and current_conn: current_conn.close()

    # --- Estoque Entradas ---
    def add_estoque_entrada(self, data):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query_entrada = "INSERT INTO estoque_entradas (produto_id, quantidade, preco_custo, fornecedor, observacao) VALUES (?, ?, ?, ?, ?)"
            params_entrada = (data['produto_id'], data['quantidade'], data.get('preco_custo'), data.get('fornecedor'), data.get('observacao'))
            cursor.execute(query_entrada, params_entrada)
            entrada_id = cursor.lastrowid
            self.update_estoque_produto(data['produto_id'], data['quantidade'], is_venda=False, conn=conn)
            conn.commit()
            return entrada_id
        except sqlite3.Error as e:
            print(f"Error in add_estoque_entrada: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: conn.close()

    def get_all_estoque_entradas(self):
        query = "SELECT ee.*, p.nome as produto_nome FROM estoque_entradas ee JOIN produtos p ON ee.produto_id = p.id ORDER BY ee.data_entrada DESC"
        return self.execute_query(query, fetch_all=True)

    # --- Vendas ---
    def save_venda_rascunho(self, venda_data, itens_data):
        venda_id = venda_data.get('id')
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if venda_id:
                cursor.execute("SELECT status FROM vendas WHERE id = ?", (venda_id,))
                current_status = cursor.fetchone()
                if not current_status or current_status['status'] != 'Rascunho':
                    raise ValueError("Apenas vendas 'Rascunho' podem ser atualizadas.")
                venda_update_query = "UPDATE vendas SET cliente_id=?, valor_total=?, observacao=?, data_venda=?, status='Rascunho', forma_pagamento=?, numero_parcelas=?, periodo_pagamento_parcelas=? WHERE id = ?"
                venda_params = (venda_data.get('cliente_id'), venda_data['valor_total'], venda_data.get('observacao'), venda_data.get('data_venda', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')), venda_data.get('forma_pagamento'), venda_data.get('numero_parcelas', 1), venda_data.get('periodo_pagamento_parcelas'), venda_id)
                cursor.execute(venda_update_query, venda_params)
                cursor.execute("DELETE FROM venda_itens WHERE venda_id = ?", (venda_id,))
            else:
                venda_insert_query = "INSERT INTO vendas (cliente_id, valor_total, observacao, status, data_venda, forma_pagamento, numero_parcelas, periodo_pagamento_parcelas) VALUES (?, ?, ?, 'Rascunho', ?, ?, ?, ?)"
                venda_params = (venda_data.get('cliente_id'), venda_data['valor_total'], venda_data.get('observacao'), venda_data.get('data_venda', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')), venda_data.get('forma_pagamento'), venda_data.get('numero_parcelas', 1), venda_data.get('periodo_pagamento_parcelas'))
                cursor.execute(venda_insert_query, venda_params)
                venda_id = cursor.lastrowid
            for item in itens_data:
                item_query = "INSERT INTO venda_itens (venda_id, produto_id, quantidade, preco_unitario_venda, subtotal) VALUES (?, ?, ?, ?, ?)"
                item_params = (venda_id, item['produto_id'], item['quantidade'], item['preco_unitario_venda'], item['subtotal'])
                cursor.execute(item_query, item_params)
            conn.commit()
            return venda_id
        except ValueError as ve:
            if conn: conn.rollback()
            raise ve
        except sqlite3.Error as e:
            if conn: conn.rollback()
            raise e
        finally:
            if conn: conn.close()

    def finalizar_venda(self, venda_id):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            venda = self.get_venda_by_id(venda_id)
            if not venda or venda['status'] != 'Rascunho':
                raise ValueError("Apenas vendas 'Rascunho' podem ser finalizadas.")
            cursor.execute("SELECT produto_id, quantidade FROM venda_itens WHERE venda_id = ?", (venda_id,))
            itens = cursor.fetchall()
            if not itens: raise ValueError("Venda sem itens não pode ser finalizada.")
            for item in itens:
                cursor.execute("SELECT nome, quantidade_estoque FROM produtos WHERE id = ?", (item['produto_id'],))
                produto_info = cursor.fetchone()
                if not produto_info: raise ValueError(f"Produto ID {item['produto_id']} não encontrado.")
                if produto_info['quantidade_estoque'] < item['quantidade']:
                    raise ValueError(f"Estoque insuficiente para {produto_info['nome']} (Disp: {produto_info['quantidade_estoque']}, Ped: {item['quantidade']})")
            for item in itens:
                self.update_estoque_produto(item['produto_id'], item['quantidade'], is_venda=True, conn=conn)
            cursor.execute("UPDATE vendas SET status = 'Concluída' WHERE id = ?", (venda_id,))
            
            data_venda_str = venda['data_venda']
            data_venda_obj = datetime.date.today() # Fallback
            if isinstance(data_venda_str, str):
                try:
                    if '/' in data_venda_str:
                        data_venda_obj = datetime.datetime.strptime(data_venda_str.split(' ')[0], '%d/%m/%Y').date()
                    else:
                        data_venda_obj = datetime.datetime.strptime(data_venda_str.split(' ')[0], '%Y-%m-%d').date()
                except ValueError:
                    print(f"Alerta: Falha ao parsear data_venda '{data_venda_str}' em finalizar_venda. Usando data atual.")
            elif isinstance(data_venda_str, (datetime.datetime, datetime.date)):
                data_venda_obj = data_venda_str.date() if isinstance(data_venda_str, datetime.datetime) else data_venda_str
            
            numero_parcelas = venda['numero_parcelas'] if venda['numero_parcelas'] else 1
            valor_total_decimal = Decimal(str(venda['valor_total']))
            valor_parcela = (valor_total_decimal / Decimal(str(numero_parcelas))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            soma_parcelas_calculadas = Decimal('0.00')

            for i in range(1, numero_parcelas + 1):
                data_vencimento_parcela = data_venda_obj
                if venda['periodo_pagamento_parcelas'] and numero_parcelas > 1:
                    if venda['periodo_pagamento_parcelas'] == 'Diário': data_vencimento_parcela = data_venda_obj + datetime.timedelta(days=i-1)
                    elif venda['periodo_pagamento_parcelas'] == 'Semanal': data_vencimento_parcela = data_venda_obj + datetime.timedelta(weeks=i-1)
                    elif venda['periodo_pagamento_parcelas'] == 'Quinzenal': data_vencimento_parcela = data_venda_obj + datetime.timedelta(days=15*(i-1))
                    elif venda['periodo_pagamento_parcelas'] == 'Mensal':
                        mes = data_venda_obj.month -1 + (i-1); ano = data_venda_obj.year + mes // 12; mes = mes % 12 + 1; dia = data_venda_obj.day
                        try: data_vencimento_parcela = datetime.date(ano, mes, dia)
                        except ValueError: import calendar; ultimo_dia_mes = calendar.monthrange(ano, mes)[1]; data_vencimento_parcela = datetime.date(ano, mes, ultimo_dia_mes)
                
                valor_parcela_atual = valor_parcela
                if i == numero_parcelas: valor_parcela_atual = valor_total_decimal - soma_parcelas_calculadas
                soma_parcelas_calculadas += valor_parcela_atual
                descricao_lancamento = f"Venda #{venda_id} - Parc. {i}/{numero_parcelas}"
                lancamento_data = {'venda_id': venda_id, 'descricao': descricao_lancamento, 'tipo': 'Receita', 'valor': float(valor_parcela_atual), 'numero_parcela_atual': i, 'total_parcelas': numero_parcelas, 'data_vencimento': data_vencimento_parcela.strftime('%Y-%m-%d'), 'status_pagamento': 'Pendente', 'forma_pagamento_efetiva': venda['forma_pagamento']}
                self.add_lancamento_financeiro(lancamento_data, conn=conn)
            conn.commit(); return True
        except ValueError as ve:
            if conn: conn.rollback()
            raise ve
        except sqlite3.Error as e:
            if conn: conn.rollback()
            raise e
        finally:
            if conn: conn.close()

    def cancelar_venda(self, venda_id):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM vendas WHERE id = ?", (venda_id,))
            venda_info = cursor.fetchone()
            if not venda_info: raise ValueError("Venda não encontrada.")
            current_status = venda_info['status']
            if current_status == 'Cancelada': raise ValueError("Venda já está cancelada.")
            if current_status == 'Rascunho':
                cursor.execute("DELETE FROM venda_itens WHERE venda_id = ?", (venda_id,))
                cursor.execute("DELETE FROM vendas WHERE id = ?", (venda_id,))
                cursor.execute("DELETE FROM lancamentos_financeiros WHERE venda_id = ? AND status_pagamento = 'Pendente'", (venda_id,))
            elif current_status == 'Concluída':
                cursor.execute("SELECT produto_id, quantidade FROM venda_itens WHERE venda_id = ?", (venda_id,))
                itens = cursor.fetchall()
                for item in itens:
                    self.update_estoque_produto(item['produto_id'], item['quantidade'], is_venda=False, conn=conn)
                cursor.execute("UPDATE vendas SET status = 'Cancelada' WHERE id = ?", (venda_id,))
                cursor.execute("UPDATE lancamentos_financeiros SET status_pagamento = 'Cancelado' WHERE venda_id = ? AND status_pagamento = 'Pendente'", (venda_id,))
            conn.commit(); return True
        except ValueError as ve:
            if conn: conn.rollback()
            raise ve
        except sqlite3.Error as e:
            if conn: conn.rollback()
            raise e
        finally:
            if conn: conn.close()

    def get_all_vendas(self):
        query = """
        SELECT
        v.*,
        c.nome as cliente_nome,
        (SELECT COUNT(*) FROM lancamentos_financeiros lf WHERE lf.venda_id = v.id AND lf.tipo = 'Receita') as total_parcelas,
        (SELECT COUNT(*) FROM lancamentos_financeiros lf WHERE lf.venda_id = v.id AND lf.tipo = 'Receita' AND lf.status_pagamento = 'Pago') as parcelas_pagas,
        (SELECT COUNT(*) FROM lancamentos_financeiros lf WHERE lf.venda_id = v.id AND lf.tipo = 'Receita' AND lf.status_pagamento IN ('Pendente', 'Vencido')) as parcelas_em_aberto
        FROM
        vendas v
        LEFT JOIN
        clientes c ON v.cliente_id = c.id
        ORDER BY
        v.data_venda DESC
        """
        return self.execute_query(query, fetch_all=True)

    def get_venda_by_id(self, venda_id):
        query = "SELECT v.*, c.nome as cliente_nome FROM vendas v LEFT JOIN clientes c ON v.cliente_id = c.id WHERE v.id = ?"
        return self.execute_query(query, (venda_id,), fetch_one=True)

    def get_venda_itens_by_venda_id(self, venda_id):
        query = "SELECT vi.*, p.nome as produto_nome, p.unidade_medida as produto_unidade FROM venda_itens vi JOIN produtos p ON vi.produto_id = p.id WHERE vi.venda_id = ?"
        return self.execute_query(query, (venda_id,), fetch_all=True) or []

    # --- Lançamentos Financeiros ---
    def add_lancamento_financeiro(self, data, conn=None, data_lancamento=None):
        query = "INSERT INTO lancamentos_financeiros (venda_id, descricao, tipo, valor, numero_parcela_atual, total_parcelas, data_vencimento, status_pagamento, forma_pagamento_efetiva, observacao, data_lancamento) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        params = (data.get('venda_id'), data['descricao'], data['tipo'], data['valor'], data.get('numero_parcela_atual', 1), data.get('total_parcelas', 1), data['data_vencimento'], data.get('status_pagamento', 'Pendente'), data.get('forma_pagamento_efetiva'), data.get('observacao'), data_lancamento if data_lancamento else datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        use_external_conn = conn is not None
        current_conn = conn if use_external_conn else self._get_connection()
        cursor = current_conn.cursor()
        try:
            cursor.execute(query, params)
            last_id = cursor.lastrowid
            if not use_external_conn:
                current_conn.commit()
            return last_id
        except sqlite3.Error as e:
            print(f"Error adding financial entry: {e}")
            if not use_external_conn and current_conn:
                current_conn.rollback()
            return None
        finally:
            if not use_external_conn and current_conn:
                current_conn.close()
    def get_valor_total_vendas_mes_atual(self):
        try:
            today = datetime.date.today()
            start_of_month = today.replace(day=1)
            query = """SELECT SUM(valor_total) FROM vendas WHERE status = 'Concluída' AND data_venda >= ?"""
            result = self.execute_query(query, (start_of_month.strftime('%Y-%m-%d'),), fetch_one=True)
            return result[0] if result and result[0] is not None else 0.0
        except Exception as e:
            print(f"Erro ao calcular valor total de vendas do mês: {e}")
            return 0.0

    def get_valor_total_vendas_ultimos_15_days(self):
        try:
            today = datetime.date.today()
            fifteen_days_ago = today - datetime.timedelta(days=15)
            query = """SELECT SUM(valor_total) FROM vendas WHERE status = 'Concluída' AND data_venda >= ?"""
            result = self.execute_query(query, (fifteen_days_ago.strftime('%Y-%m-%d'),), fetch_one=True)
            return result[0] if result and result[0] is not None else 0.0
        except Exception as e:
            print(f"Erro ao calcular valor total de vendas dos últimos 15 dias: {e}")
            return 0.0

    def get_total_clientes_com_vendas(self):
        try:
            query = """SELECT COUNT(DISTINCT cliente_id) FROM vendas WHERE status = 'Concluída' AND cliente_id IS NOT NULL"""
            result = self.execute_query(query, fetch_one=True)
            return result[0] if result and result[0] is not None else 0
        except Exception as e:
            print(f"Erro ao contar clientes com vendas: {e}")
            return 0

    def get_maior_valor_venda(self):
        try:
            query = """SELECT MAX(valor_total) FROM vendas WHERE status = 'Concluída'"""
            result = self.execute_query(query, fetch_one=True)
            return result[0] if result and result[0] is not None else 0.0
        except Exception as e:
            print(f"Erro ao buscar maior valor de venda: {e}")
            return 0.0

    def get_ticket_medio_vendas(self):
        try:
            query_total = """SELECT SUM(valor_total) FROM vendas WHERE status = 'Concluída'"""
            total_vendas_result = self.execute_query(query_total, fetch_one=True)
            total_vendas = total_vendas_result[0] if total_vendas_result else None

            query_count = """SELECT COUNT(*) FROM vendas WHERE status = 'Concluída'"""
            count_vendas_result = self.execute_query(query_count, fetch_one=True)
            count_vendas = count_vendas_result[0] if count_vendas_result else None

            if count_vendas is not None and count_vendas > 0 and total_vendas is not None:
                return total_vendas / count_vendas
            else:
                return 0.0
        except Exception as e:
            print(f"Erro ao calcular ticket médio: {e}")
            return 0.0

    def get_all_lancamentos_financeiros(self, filtro_status=None, filtro_tipo=None, data_inicio=None, data_fim=None, order_by="data_vencimento ASC, id ASC"):
        query_str = "SELECT lf.*, v.id as venda_numero FROM lancamentos_financeiros lf LEFT JOIN vendas v ON lf.venda_id = v.id"
        conditions = []; params = []
        if filtro_status: conditions.append("lf.status_pagamento = ?"); params.append(filtro_status)
        if filtro_tipo: conditions.append("lf.tipo = ?"); params.append(filtro_tipo)
        
        # Adiciona condições de data
        if data_inicio:
            conditions.append("lf.data_vencimento >= ?")
            params.append(data_inicio)
        if data_fim:
            conditions.append("lf.data_vencimento <= ?")
            params.append(data_fim)

        if conditions: query_str += " WHERE " + " AND ".join(conditions)
        query_str += f" ORDER BY {order_by}"
        
        return self.execute_query(query_str, params, fetch_all=True)

    def update_status_lancamento(self, lancamento_id, novo_status, data_pagamento=None, forma_pagamento_efetiva=None):
        if novo_status == 'Pago' and not data_pagamento:
            data_pagamento = datetime.date.today().strftime('%Y-%m-%d')
        if novo_status != 'Pago':
            data_pagamento = None
            forma_pagamento_efetiva = None
        query = "UPDATE lancamentos_financeiros SET status_pagamento = ?, data_pagamento = ?, forma_pagamento_efetiva = ? WHERE id = ?"
        params = (novo_status, data_pagamento, forma_pagamento_efetiva, lancamento_id)
        return self.execute_query(query, params)

    def delete_lancamento_financeiro(self, lancamento_id):
        return self.execute_query("DELETE FROM lancamentos_financeiros WHERE id = ?", (lancamento_id,))

    # --- Dashboard Data ---
    def get_dashboard_stats(self):
        stats = {}
        def get_count_or_zero(query, params=()):
            result = self.execute_query(query, params, fetch_one=True)
            return result['count'] if result and result['count'] is not None else 0
        def get_sum_or_zero(query, params=()):
            result = self.execute_query(query, params, fetch_one=True)
            return result['sum'] if result and result['sum'] is not None else 0.0

        stats['total_clientes'] = get_count_or_zero("SELECT COUNT(*) as count FROM clientes")
        stats['total_grupos'] = get_count_or_zero("SELECT COUNT(*) as count FROM grupos")
        stats['total_categorias'] = get_count_or_zero("SELECT COUNT(*) as count FROM categorias")
        stats['total_produtos'] = get_count_or_zero("SELECT COUNT(*) as count FROM produtos")
        
        stats['total_vendas_mes_atual'] = get_count_or_zero("SELECT COUNT(DISTINCT id) as count FROM vendas WHERE strftime('%Y-%m', data_venda, 'localtime') = strftime('%Y-%m', 'now', 'localtime') AND status = 'Concluída'")
        stats['valor_total_vendas_mes_atual'] = get_sum_or_zero("SELECT SUM(valor_total) as sum FROM vendas WHERE strftime('%Y-%m', data_venda, 'localtime') = strftime('%Y-%m', 'now', 'localtime') AND status = 'Concluída'")
        
        stats['a_receber_total'] = get_sum_or_zero("SELECT SUM(valor) as sum FROM lancamentos_financeiros WHERE tipo = 'Receita' AND status_pagamento = 'Pendente'")
        stats['a_pagar_total'] = get_sum_or_zero("SELECT SUM(valor) as sum FROM lancamentos_financeiros WHERE tipo = 'Despesa' AND status_pagamento = 'Pendente'")
        
        stats['recebido_mes_atual'] = get_sum_or_zero("SELECT SUM(valor) as sum FROM lancamentos_financeiros WHERE tipo = 'Receita' AND status_pagamento = 'Pago' AND strftime('%Y-%m', data_pagamento, 'localtime') = strftime('%Y-%m', 'now', 'localtime')")
        stats['pago_mes_atual'] = get_sum_or_zero("SELECT SUM(valor) as sum FROM lancamentos_financeiros WHERE tipo = 'Despesa' AND status_pagamento = 'Pago' AND strftime('%Y-%m', data_pagamento, 'localtime') = strftime('%Y-%m', 'now', 'localtime')")

        stats['produtos_baixo_estoque'] = self.execute_query("SELECT * FROM produtos WHERE quantidade_estoque <= 5 ORDER BY quantidade_estoque ASC LIMIT 5", fetch_all=True) or []
        stats['vendas_recentes'] = self.execute_query("SELECT v.id, v.data_venda, v.valor_total, c.nome as cliente_nome, v.status FROM vendas v LEFT JOIN clientes c ON v.cliente_id = c.id ORDER BY v.data_venda DESC LIMIT 5", fetch_all=True) or []
        return stats

    def get_vendas_last_7_days(self):
        query = """
        SELECT strftime('%Y-%m-%d', data_venda, 'localtime') as periodo, SUM(valor_total) as total_vendas
        FROM vendas
        WHERE status = 'Concluída'
        AND data_venda >= date('now', '-7 days')
        GROUP BY periodo
        ORDER BY periodo ASC
        """
        return self.execute_query(query, fetch_all=True) or []

    def get_vendas_last_30_days(self):
        query = """
        SELECT strftime('%Y-%m-%d', data_venda, 'localtime') as periodo, SUM(valor_total) as total_vendas
        FROM vendas
        WHERE status = 'Concluída'
        AND data_venda >= date('now', '-30 days')
        GROUP BY periodo
        ORDER BY periodo ASC
        """
        return self.execute_query(query, fetch_all=True) or []

    def get_vendas_monthly(self):
        query = """    
        SELECT strftime('%Y-%m', data_venda, 'localtime') as periodo, SUM(valor_total) as total_vendas
        FROM vendas
        WHERE status = 'Concluída'
        AND strftime('%Y', data_venda, 'localtime') = strftime('%Y', 'now', 'localtime')
        GROUP BY periodo
        ORDER BY periodo ASC
        """
        return self.execute_query(query, fetch_all=True) or []

    def get_vendas_quarterly(self):
        query = """    
        SELECT
            strftime('%Y', data_venda, 'localtime') || '-Q' || (
                CAST(strftime('%m', data_venda, 'localtime') AS INTEGER) - 1
            ) / 3 + 1 AS periodo,
            SUM(valor_total) AS total_vendas
        FROM vendas
        WHERE status = 'Concluída'
        AND data_venda >= date('now', '-1 year') -- Para pegar os últimos 4 trimestres
        GROUP BY periodo
        ORDER BY periodo ASC
        """
        return self.execute_query(query, fetch_all=True) or []

    def get_vendas_semiannually(self):
        query = """    
        SELECT
            strftime('%Y', data_venda, 'localtime') || '-S' || (
                CAST(strftime('%m', data_venda, 'localtime') AS INTEGER) - 1
            ) / 6 + 1 AS periodo,
            SUM(valor_total) AS total_vendas
        FROM vendas
        WHERE status = 'Concluída'
        AND data_venda >= date('now', '-1 year') -- Para pegar os últimos 2 semestres
        GROUP BY periodo
        ORDER BY periodo ASC
        """
        return self.execute_query(query, fetch_all=True) or []

    def get_vendas_annually(self):
        query = """
        SELECT strftime('%Y', data_venda, 'localtime') as periodo, SUM(valor_total) as total_vendas
        FROM vendas
        WHERE status = 'Concluída'
        AND data_venda >= date('now', '-5 years') -- Para pegar os últimos 5 anos
        GROUP BY periodo
        ORDER BY periodo ASC
        """
        return self.execute_query(query, fetch_all=True) or []

db_manager = DatabaseManager(DB_NAME)
