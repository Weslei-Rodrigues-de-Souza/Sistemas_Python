import os
import datetime
import sqlite3
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from database import db_manager, DB_NAME # Seu database.py (sales_system_database_py_v10)
from decimal import Decimal

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Configurações de Upload ---
UPLOAD_FOLDER_BASE = os.path.join(app.root_path, 'static', 'uploads')
PRODUCT_IMAGE_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER_BASE, 'product_images')
app.config['PRODUCT_IMAGE_UPLOAD_FOLDER'] = PRODUCT_IMAGE_UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(PRODUCT_IMAGE_UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Funções Utilitárias ---
def format_datetime_for_display(dt_str):
    if not dt_str: return "N/A"
    try:
        if isinstance(dt_str, (datetime.datetime, datetime.date)):
            return dt_str.strftime('%d/%m/%Y %H:%M') if isinstance(dt_str, datetime.datetime) else dt_str.strftime('%d/%m/%Y')
        dt_str_cleaned = str(dt_str).replace('Z', '')
        if 'T' in dt_str_cleaned: dt_obj = datetime.datetime.fromisoformat(dt_str_cleaned); return dt_obj.strftime('%d/%m/%Y %H:%M')
        elif ' ' in dt_str_cleaned: dt_obj = datetime.datetime.strptime(dt_str_cleaned, '%Y-%m-%d %H:%M:%S'); return dt_obj.strftime('%d/%m/%Y %H:%M')
        else: dt_obj = datetime.datetime.strptime(dt_str_cleaned, '%Y-%m-%d'); return dt_obj.strftime('%d/%m/%Y')
    except (ValueError, TypeError): return str(dt_str)

def format_date_for_input(date_str_iso):
    if not date_str_iso: return ""
    try:
        if isinstance(date_str_iso, (datetime.date, datetime.datetime)): return date_str_iso.strftime('%Y-%m-%d')
        if '/' in str(date_str_iso): # Try to parse DD/MM/YYYY
            parts = str(date_str_iso).split(' ')[0].split('/')
            if len(parts) == 3: return f"{parts[2]}-{parts[1]}-{parts[0]}"
        dt_obj = datetime.datetime.fromisoformat(str(date_str_iso).split(' ')[0].split('T')[0])
        return dt_obj.strftime('%Y-%m-%d')
    except (ValueError, TypeError): return str(date_str_iso)

app.jinja_env.filters['datetime_display'] = format_datetime_for_display
app.jinja_env.filters['date_input'] = format_date_for_input

@app.context_processor
def inject_now(): return {'now': datetime.datetime.now()}

# --- Rotas ---
@app.route('/')
def dashboard():
    try:
        stats = db_manager.get_dashboard_stats()
        stats['a_receber_total'] = Decimal(stats.get('a_receber_total') if stats.get('a_receber_total') is not None else 0.0)
        stats['a_pagar_total'] = Decimal(stats.get('a_pagar_total') if stats.get('a_pagar_total') is not None else 0.0)
        stats['recebido_mes_atual'] = Decimal(stats.get('recebido_mes_atual') if stats.get('recebido_mes_atual') is not None else 0.0)
        stats['pago_mes_atual'] = Decimal(stats.get('pago_mes_atual') if stats.get('pago_mes_atual') is not None else 0.0)
        stats['valor_total_vendas_mes_atual'] = Decimal(stats.get('valor_total_vendas_mes_atual') if stats.get('valor_total_vendas_mes_atual') is not None else 0.0)
    except Exception as e:
        flash(f"Erro ao carregar estatísticas do dashboard: {e}", "danger")
        stats = {
            'total_clientes': 0, 'total_grupos': 0, 'total_categorias': 0, 'total_produtos': 0,
            'total_vendas_mes_atual': 0, 'valor_total_vendas_mes_atual': Decimal('0.00'),
            'a_receber_total': Decimal('0.00'), 'a_pagar_total': Decimal('0.00'),
            'recebido_mes_atual': Decimal('0.00'), 'pago_mes_atual': Decimal('0.00'),
            'produtos_baixo_estoque': [], 'vendas_recentes': []
        }
    return render_template('dashboard.html', stats=stats)

# --- Grupos ---
@app.route('/grupos')
def grupos_lista():
    search = request.args.get('search', '')
    try:
        grupos = db_manager.get_all_grupos(search)
    except Exception as e:
        flash(f"Erro ao carregar grupos: {e}", "danger")
        grupos = []
    return render_template('grupos.html', grupos=grupos, search_query=search)

@app.route('/grupo/novo', methods=['POST'])
def grupo_novo():
    data = {'nome': request.form.get('nome_grupo'), 'descricao': request.form.get('descricao_grupo')}
    if not data['nome']:
        flash('Nome do grupo é obrigatório.', 'danger')
    else:
        try:
            if db_manager.add_grupo(data):
                flash('Grupo adicionado com sucesso!', 'success')
            else:
                flash('Erro ao adicionar grupo. Nome do grupo já pode existir.', 'danger')
        except Exception as e:
            flash(f"Erro ao salvar grupo: {e}", "danger")
    return redirect(url_for('grupos_lista'))

@app.route('/grupo/editar/<int:grupo_id>', methods=['POST'])
def grupo_editar(grupo_id):
    data = {'nome': request.form.get('edit_nome_grupo'), 'descricao': request.form.get('edit_descricao_grupo')}
    if not data['nome']:
        flash('Nome do grupo é obrigatório.', 'danger')
    else:
        try:
            if db_manager.update_grupo(grupo_id, data):
                flash('Grupo atualizado com sucesso!', 'success')
            else:
                flash('Erro ao atualizar grupo. Nome do grupo já pode existir.', 'danger')
        except Exception as e:
            flash(f"Erro ao atualizar grupo: {e}", "danger")
    return redirect(url_for('grupos_lista'))

@app.route('/grupo/json/<int:grupo_id>')
def grupo_json(grupo_id):
    try:
        grupo = db_manager.get_grupo_by_id(grupo_id)
        if grupo:
            return jsonify(dict(grupo))
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar grupo: {str(e)}'}), 500
    return jsonify({'error': 'Grupo não encontrado'}), 404

@app.route('/grupo/excluir/<int:grupo_id>', methods=['POST'])
def grupo_excluir(grupo_id):
    try:
        if db_manager.delete_grupo(grupo_id):
            flash('Grupo excluído com sucesso!', 'success')
        else:
            flash('Erro ao excluir grupo.', 'danger')
    except Exception as e:
        flash(f"Erro ao excluir grupo: {e}", "danger")
    return redirect(url_for('grupos_lista'))

# --- Categorias ---
@app.route('/categorias')
def categorias_lista():
    search = request.args.get('search', '')
    try:
        categorias = db_manager.get_all_categorias(search)
        grupos = db_manager.get_all_grupos()
    except Exception as e:
        flash(f"Erro ao carregar categorias ou grupos: {e}", "danger")
        categorias = []
        grupos = []
    return render_template('categorias.html', categorias=categorias, grupos=grupos, search_query=search)

@app.route('/categoria/nova', methods=['POST'])
def categoria_nova():
    grupo_id_str = request.form.get('grupo_id_categoria')
    data = {
        'nome': request.form.get('nome_categoria'),
        'descricao': request.form.get('descricao_categoria'),
        'grupo_id': int(grupo_id_str) if grupo_id_str and grupo_id_str.lower() != "none" else None
    }
    if not data['nome']:
        flash('Nome da categoria é obrigatório.', 'danger')
    else:
        try:
            db_manager.add_categoria(data)
            flash('Categoria adicionada com sucesso!', 'success')
        except sqlite3.IntegrityError:
             flash('Erro: Já existe uma categoria com este nome neste grupo.', 'danger')
        except Exception as e:
            flash(f"Erro ao salvar categoria: {e}", "danger")
    return redirect(url_for('categorias_lista'))

@app.route('/categoria/editar/<int:categoria_id>', methods=['POST'])
def categoria_editar(categoria_id):
    grupo_id_str = request.form.get('edit_grupo_id_categoria')
    data = {
        'nome': request.form.get('edit_nome_categoria'),
        'descricao': request.form.get('edit_descricao_categoria'),
        'grupo_id': int(grupo_id_str) if grupo_id_str and grupo_id_str.lower() != "none" else None
    }
    if not data['nome']:
        flash('Nome da categoria é obrigatório.', 'danger')
    else:
        try:
            db_manager.update_categoria(categoria_id, data)
            flash('Categoria atualizada com sucesso!', 'success')
        except sqlite3.IntegrityError:
             flash('Erro: Já existe uma categoria com este nome neste grupo.', 'danger')
        except Exception as e:
            flash(f"Erro ao atualizar categoria: {e}", "danger")
    return redirect(url_for('categorias_lista'))

@app.route('/categoria/json/<int:categoria_id>')
def categoria_json(categoria_id):
    try:
        categoria = db_manager.get_categoria_by_id(categoria_id)
        if categoria:
            return jsonify(dict(categoria))
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar categoria: {str(e)}'}), 500
    return jsonify({'error': 'Categoria não encontrada'}), 404

@app.route('/categoria/excluir/<int:categoria_id>', methods=['POST'])
def categoria_excluir(categoria_id):
    try:
        if db_manager.delete_categoria(categoria_id):
            flash('Categoria excluída com sucesso!', 'success')
        else:
            flash('Erro ao excluir categoria. Verifique se está em uso por algum produto.', 'danger')
    except Exception as e:
        flash(f"Erro ao excluir categoria: {e}", "danger")
    return redirect(url_for('categorias_lista'))

# --- Clientes ---
@app.route('/clientes')
def clientes_lista():
    search = request.args.get('search', '')
    try:
        clientes = db_manager.get_all_clientes(search)
    except Exception as e:
        flash(f"Erro ao carregar clientes: {e}", "danger")
        clientes = []
    return render_template('clientes.html', clientes=clientes, search_query=search)

@app.route('/cliente/novo', methods=['POST'])
def cliente_novo():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome_cliente'),
            'email': request.form.get('email_cliente'),
            'telefone': request.form.get('telefone_cliente'),
            'endereco_rua': request.form.get('endereco_rua_cliente'),
            'endereco_numero': request.form.get('endereco_numero_cliente'),
            'endereco_bairro': request.form.get('endereco_bairro_cliente'),
            'endereco_cidade': request.form.get('endereco_cidade_cliente'),
            'endereco_uf': request.form.get('endereco_uf_cliente'),
            'endereco_cep': request.form.get('endereco_cep_cliente')
        }
        if not data['nome']:
            flash('Nome do cliente é obrigatório.', 'danger')
        else:
            try:
                cliente_id = db_manager.add_cliente(data)
                if cliente_id:
                    flash('Cliente adicionado com sucesso!', 'success')
                else:
                    flash('Erro ao adicionar cliente.', 'danger')
            except Exception as e:
                flash(f"Erro ao salvar cliente: {e}", "danger")
        return redirect(url_for('clientes_lista'))

@app.route('/cliente/editar/<int:cliente_id>', methods=['POST'])
def cliente_editar(cliente_id):
    if request.method == 'POST':
        data = {
            'nome': request.form.get('edit_nome_cliente'),
            'email': request.form.get('edit_email_cliente'),
            'telefone': request.form.get('edit_telefone_cliente'),
            'endereco_rua': request.form.get('edit_endereco_rua_cliente'),
            'endereco_numero': request.form.get('edit_endereco_numero_cliente'),
            'endereco_bairro': request.form.get('edit_endereco_bairro_cliente'),
            'endereco_cidade': request.form.get('edit_endereco_cidade_cliente'),
            'endereco_uf': request.form.get('edit_endereco_uf_cliente'),
            'endereco_cep': request.form.get('edit_endereco_cep_cliente')
        }
        if not data['nome']:
            flash('Nome do cliente é obrigatório.', 'danger')
        else:
            try:
                if db_manager.update_cliente(cliente_id, data):
                    flash('Cliente atualizado com sucesso!', 'success')
                else:
                    flash('Erro ao atualizar cliente.', 'danger')
            except Exception as e:
                flash(f"Erro ao atualizar cliente: {e}", "danger")
        return redirect(url_for('clientes_lista'))

@app.route('/cliente/json/<int:cliente_id>')
def cliente_json(cliente_id):
    try:
        cliente = db_manager.get_cliente_by_id(cliente_id)
        if cliente:
            return jsonify(dict(cliente))
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar cliente: {str(e)}'}), 500
    return jsonify({'error': 'Cliente não encontrado'}), 404

@app.route('/cliente/excluir/<int:cliente_id>', methods=['POST'])
def cliente_excluir(cliente_id):
    try:
        if db_manager.delete_cliente(cliente_id):
            flash('Cliente excluído com sucesso!', 'success')
        else:
            flash('Erro ao excluir cliente.', 'danger')
    except Exception as e:
        flash(f"Erro ao excluir cliente: {e}", "danger")
    return redirect(url_for('clientes_lista'))

# --- Produtos ---
@app.route('/produtos')
def produtos_lista():
    search = request.args.get('search', '')
    try:
        produtos = db_manager.get_all_produtos(search)
        categorias = db_manager.get_all_categorias()
    except Exception as e:
        flash(f"Erro ao carregar produtos ou categorias: {e}", "danger")
        produtos = []
        categorias = []
    return render_template('produtos.html', produtos=produtos, categorias=categorias, search_query=search)

@app.route('/produto/novo', methods=['POST'])
def produto_novo():
    if request.method == 'POST':
        try:
            cat_id_str = request.form.get('categoria_id_produto')
            data = {'nome': request.form.get('nome_produto'),'descricao': request.form.get('descricao_produto'),'preco_venda': float(request.form.get('preco_venda_produto')),'quantidade_estoque': int(request.form.get('quantidade_estoque_produto', 0)),'unidade_medida': request.form.get('unidade_medida_produto'),'categoria_id': int(cat_id_str) if cat_id_str and cat_id_str.lower() != "none" else None}
            if not data['nome'] or data['preco_venda'] is None or data['preco_venda'] < 0:
                flash('Nome e Preço de Venda (positivo) são obrigatórios.', 'danger')
            elif data['quantidade_estoque'] < 0:
                flash('Estoque não pode ser negativo.', 'danger')
            else:
                produto_id = db_manager.add_produto(data)
                if produto_id:
                    flash('Produto adicionado! Adicione imagens na edição.', 'success')
                    files = request.files.getlist('imagens_produto')
                    for file in files:
                        if file and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            unique_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
                            file_path = os.path.join(app.config['PRODUCT_IMAGE_UPLOAD_FOLDER'], unique_filename)
                            file.save(file_path)
                            db_manager.add_produto_imagem(produto_id, unique_filename)
                        elif file and file.filename != '':
                            flash(f"Tipo de arquivo não permitido para '{file.filename}'.", 'warning')
                else:
                    flash('Erro ao adicionar produto. Nome já existe?', 'danger')
        except ValueError:
            flash('Valor inválido para preço ou quantidade.', 'danger')
        except Exception as e:
            flash(f'Erro ao adicionar produto: {str(e)}', 'danger')
        return redirect(url_for('produtos_lista'))

@app.route('/produto/editar/<int:produto_id>', methods=['POST'])
def produto_editar(produto_id):
    if request.method == 'POST':
        try:
            cat_id_str = request.form.get('edit_categoria_id_produto')
            data = {'nome': request.form.get('edit_nome_produto'),'descricao': request.form.get('edit_descricao_produto'),'preco_venda': float(request.form.get('edit_preco_venda_produto')),'quantidade_estoque': int(request.form.get('edit_quantidade_estoque_produto', 0)),'unidade_medida': request.form.get('edit_unidade_medida_produto'),'categoria_id': int(cat_id_str) if cat_id_str and cat_id_str.lower() != "none" else None}
            if not data['nome'] or data['preco_venda'] is None or data['preco_venda'] < 0:
                flash('Nome e Preço de Venda (positivo) são obrigatórios.', 'danger')
            elif data['quantidade_estoque'] < 0:
                flash('Estoque não pode ser negativo.', 'danger')
            else:
                if db_manager.update_produto(produto_id, data):
                    flash('Produto atualizado!', 'success')
                    files = request.files.getlist('edit_imagens_produto')
                    for file in files:
                        if file and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            unique_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
                            file_path = os.path.join(app.config['PRODUCT_IMAGE_UPLOAD_FOLDER'], unique_filename)
                            file.save(file_path)
                            db_manager.add_produto_imagem(produto_id, unique_filename)
                        elif file and file.filename != '':
                             flash(f"Tipo de arquivo não permitido para '{file.filename}'.", 'warning')
                    imagens_a_remover_ids = request.form.getlist('remover_imagem_ids')
                    for img_id_str in imagens_a_remover_ids:
                        try:
                            db_manager.delete_produto_imagem(int(img_id_str), app.config['PRODUCT_IMAGE_UPLOAD_FOLDER'])
                        except ValueError:
                            flash(f"ID de imagem inválido para remoção: {img_id_str}", "warning")
                else:
                    flash('Erro ao atualizar produto. Nome já existe?', 'danger')
        except ValueError:
            flash('Valor inválido para preço ou quantidade.', 'danger')
        except Exception as e:
            flash(f'Erro ao atualizar produto: {str(e)}', 'danger')
        return redirect(url_for('produtos_lista'))

@app.route('/produto/json/<int:produto_id>')
def produto_json(produto_id):
    try:
        produto_row = db_manager.get_produto_by_id(produto_id)
        if produto_row:
            produto_dict = dict(produto_row)
            imagens_db = db_manager.get_imagens_por_produto_id(produto_id)
            produto_dict['imagens'] = [dict(img) for img in imagens_db] if imagens_db else []
            return jsonify(produto_dict)
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar produto: {str(e)}'}), 500
    return jsonify({'error': 'Produto não encontrado'}), 404

@app.route('/produto/imagem/excluir/<int:imagem_id>', methods=['POST'])
def produto_imagem_excluir(imagem_id):
    try:
        if db_manager.delete_produto_imagem(imagem_id, app.config['PRODUCT_IMAGE_UPLOAD_FOLDER']):
            return jsonify({'success': True, 'message': 'Imagem excluída.'})
        else:
            return jsonify({'success': False, 'message': 'Erro ao excluir imagem.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/produto/excluir/<int:produto_id>', methods=['POST'])
def produto_excluir(produto_id):
    try:
        if db_manager.delete_produto(produto_id, app.config['PRODUCT_IMAGE_UPLOAD_FOLDER']):
            flash('Produto e suas imagens foram excluídos com sucesso!', 'success')
        else:
            flash('Erro ao excluir produto. Pode estar associado a vendas.', 'danger')
    except Exception as e:
        flash(f"Erro ao excluir produto: {e}", "danger")
    return redirect(url_for('produtos_lista'))

# --- Estoque Entradas ---
@app.route('/estoque/entradas', methods=['GET', 'POST'])
def estoque_entradas():
    if request.method == 'POST':
        try:
            data = {'produto_id': int(request.form['produto_id_entrada']), 'quantidade': int(request.form['quantidade_entrada']), 'preco_custo': float(request.form.get('preco_custo_entrada')) if request.form.get('preco_custo_entrada') else None, 'fornecedor': request.form.get('fornecedor_entrada'), 'observacao': request.form.get('observacao_entrada')}
            if not data['produto_id'] or data['quantidade'] <= 0:
                flash('Produto e Quantidade (positiva) são obrigatórios.', 'danger')
            elif data['preco_custo'] is not None and data['preco_custo'] < 0:
                flash('Preço de custo não pode ser negativo.', 'danger')
            else:
                if db_manager.add_estoque_entrada(data):
                    flash('Entrada de estoque registrada com sucesso!', 'success')
                else:
                    flash('Erro ao registrar entrada de estoque.', 'danger')
        except ValueError:
            flash('Valores inválidos para quantidade ou preço de custo.', 'danger')
        except Exception as e:
            flash(f'Erro ao registrar entrada: {str(e)}', 'danger')
        return redirect(url_for('estoque_entradas'))
    try:
        grupos_all = db_manager.get_all_grupos()
        entradas_all = db_manager.get_all_estoque_entradas()
    except Exception as e:
        flash(f"Erro ao carregar dados para entrada de estoque: {e}", "danger")
        grupos_all = []
        entradas_all = []
    return render_template('estoque_entradas.html', grupos=grupos_all, entradas=entradas_all)

# --- Endpoints API para Dropdowns Dependentes ---
@app.route('/api/categorias_por_grupo/<int:grupo_id>')
def api_categorias_por_grupo(grupo_id):
    try:
        query = "SELECT id, nome FROM categorias WHERE grupo_id = ? ORDER BY nome ASC"
        categorias = db_manager.execute_query(query, (grupo_id,), fetch_all=True)
        return jsonify([dict(cat) for cat in categorias if cat])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/produtos_por_categoria/<int:categoria_id>')
def api_produtos_por_categoria(categoria_id):
    try:
        query = "SELECT id, nome, quantidade_estoque, preco_venda, unidade_medida FROM produtos WHERE categoria_id = ? ORDER BY nome ASC"
        produtos = db_manager.execute_query(query, (categoria_id,), fetch_all=True)
        return jsonify([dict(prod) for prod in produtos if prod])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Vendas ---
@app.route('/vendas')
def vendas_lista_page():
    try:
        vendas = db_manager.get_all_vendas()
        clientes_all = db_manager.get_all_clientes()
        grupos_all = db_manager.get_all_grupos()
    except Exception as e:
        flash(f"Erro ao carregar dados para a página de vendas: {e}", "danger")
        vendas = []
        clientes_all = []
        grupos_all = []
    return render_template('vendas_lista.html', vendas=vendas, clientes=clientes_all, grupos=grupos_all)

@app.route('/venda/salvar', methods=['POST'])
def venda_salvar():
    try:
        venda_id_str = request.form.get('venda_id_modal')
        venda_id = int(venda_id_str) if venda_id_str else None
        cliente_id_str = request.form.get('cliente_id_venda_modal')
        cliente_id = int(cliente_id_str) if cliente_id_str and cliente_id_str.lower() != "none" else None
        observacao_venda = request.form.get('observacao_venda_modal')
        itens_json = request.form.get('itens_venda_json_modal')
        data_venda_str = request.form.get('data_venda_modal')
        forma_pagamento = request.form.get('forma_pagamento_modal')
        numero_parcelas_str = request.form.get('numero_parcelas_modal')
        numero_parcelas = int(numero_parcelas_str) if numero_parcelas_str and forma_pagamento == 'Cartão de Crédito' else 1
        periodo_pagamento_parcelas = request.form.get('periodo_pagamento_parcelas_modal') if numero_parcelas > 1 else None

        if not itens_json:
            flash('Adicione pelo menos um item à venda.', 'danger')
            return redirect(url_for('vendas_lista_page'))
        itens_data_form = json.loads(itens_json)
        if not itens_data_form:
            flash('Nenhum item válido na venda.', 'danger')
            return redirect(url_for('vendas_lista_page'))
        valor_total_venda = sum(float(item['subtotal']) for item in itens_data_form)
        data_venda_dt = datetime.datetime.now()
        if data_venda_str:
            try:
                data_venda_dt = datetime.datetime.strptime(data_venda_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash("Formato de data da venda inválido. Usando data atual.", "warning")
        venda_data = {
            'id': venda_id, 'cliente_id': cliente_id, 'valor_total': valor_total_venda,
            'observacao': observacao_venda, 'data_venda': data_venda_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'forma_pagamento': forma_pagamento, 'numero_parcelas': numero_parcelas,
            'periodo_pagamento_parcelas': periodo_pagamento_parcelas
        }
        db_itens_data = [{'produto_id': int(item_form['produtoId']), 'quantidade': int(item_form['quantidade']), 'preco_unitario_venda': float(item_form['precoUnitario']), 'subtotal': float(item_form['subtotal'])} for item_form in itens_data_form]
        saved_venda_id = db_manager.save_venda_rascunho(venda_data, db_itens_data)
        if saved_venda_id:
            flash(f'Venda Rascunho # {saved_venda_id} {"atualizada" if venda_id else "salva"} com sucesso!', 'success')
        else:
            flash('Erro ao salvar rascunho da venda.', 'danger')
    except ValueError as ve:
        flash(f'{str(ve)}', 'danger')
    except Exception as e:
        flash(f'Ocorreu um erro inesperado ao salvar a venda: {str(e)}', 'danger')
    return redirect(url_for('vendas_lista_page'))

@app.route('/venda/rascunho/json/<int:venda_id>')
def venda_rascunho_json(venda_id):
    try:
        venda = db_manager.get_venda_by_id(venda_id)
        if not venda or venda['status'] != 'Rascunho':
            return jsonify({'error': 'Rascunho de venda não encontrado ou não é um rascunho.'}), 404
        itens = db_manager.get_venda_itens_by_venda_id(venda_id)
        itens_com_detalhes = []
        for item_row in itens:
            item = dict(item_row)
            produto_detalhes = db_manager.get_produto_by_id(item['produto_id'])
            if produto_detalhes:
                item['categoria_id'] = produto_detalhes['categoria_id']
                item['grupo_id'] = produto_detalhes['grupo_id']
            else:
                item['categoria_id'] = None; item['grupo_id'] = None
            itens_com_detalhes.append(item)
        return jsonify({'venda': dict(venda), 'itens': itens_com_detalhes})
    except Exception as e:
        return jsonify({'error': f'Erro ao buscar dados do rascunho: {str(e)}'}), 500

@app.route('/venda/finalizar/<int:venda_id>', methods=['POST'])
def venda_finalizar(venda_id):
    try:
        if db_manager.finalizar_venda(venda_id):
            flash(f'Venda #{venda_id} finalizada! Estoque e financeiro atualizados.', 'success')
    except ValueError as ve:
        flash(f'Erro ao finalizar venda #{venda_id}: {str(ve)}', 'danger')
    except Exception as e:
        flash(f'Erro inesperado ao finalizar venda #{venda_id}: {str(e)}', 'danger')
    return redirect(url_for('vendas_lista_page'))

@app.route('/venda/cancelar/<int:venda_id>', methods=['POST'])
def venda_cancelar(venda_id):
    try:
        venda_info = db_manager.get_venda_by_id(venda_id)
        if not venda_info:
            flash(f'Venda #{venda_id} não encontrada.', 'warning')
            return redirect(url_for('vendas_lista_page'))
        status_anterior = venda_info['status']
        if db_manager.cancelar_venda(venda_id):
            if status_anterior == 'Rascunho':
                flash(f'Rascunho #{venda_id} removido.', 'success')
            else:
                flash(f'Venda #{venda_id} cancelada.', 'success')
    except ValueError as ve:
        flash(f'Erro ao cancelar venda #{venda_id}: {str(ve)}', 'danger')
    except Exception as e:
        flash(f'Erro inesperado ao cancelar venda #{venda_id}: {str(e)}', 'danger')
    return redirect(url_for('vendas_lista_page'))

@app.route('/venda/view/<int:venda_id>')
def view_venda_page(venda_id):
    try:
        venda = db_manager.get_venda_by_id(venda_id)
        if not venda:
            flash('Venda não encontrada.', 'danger')
            return redirect(url_for('vendas_lista_page'))
        if venda['status'] == 'Rascunho':
             flash('Este é um rascunho. Edite na lista de vendas.', 'info')
             return redirect(url_for('vendas_lista_page'))
        itens = db_manager.get_venda_itens_by_venda_id(venda_id)
    except Exception as e:
        flash(f"Erro ao carregar detalhes da venda: {e}", "danger")
        return redirect(url_for('vendas_lista_page'))
    return render_template('view_venda.html', venda=dict(venda), itens=itens)

# --- Lançamentos Financeiros ---
@app.route('/financeiro', methods=['GET'])
def financeiro_lista():
    try:
        filtro_status = request.args.get('filtro_status', None)
        filtro_tipo = request.args.get('filtro_tipo', None)
        lancamentos_rows = db_manager.get_all_lancamentos_financeiros(
            filtro_status=filtro_status if filtro_status and filtro_status != "Todos" else None,
            filtro_tipo=filtro_tipo if filtro_tipo and filtro_tipo != "Todos" else None
        )
        saldo_acumulado = Decimal('0.00')
        lancamentos_com_saldo = []
        if lancamentos_rows: # Verifica se lancamentos_rows não é None
            for lanc_row in lancamentos_rows:
                lanc = dict(lanc_row)
                valor = Decimal(str(lanc['valor']))
                if lanc['tipo'] == 'Receita': saldo_acumulado += valor
                elif lanc['tipo'] == 'Despesa': saldo_acumulado -= valor
                lanc['saldo_acumulado'] = saldo_acumulado
                lancamentos_com_saldo.append(lanc)
        
        stats = db_manager.get_dashboard_stats()
        stats['a_receber_total'] = Decimal(stats.get('a_receber_total') if stats.get('a_receber_total') is not None else 0.0)
        stats['a_pagar_total'] = Decimal(stats.get('a_pagar_total') if stats.get('a_pagar_total') is not None else 0.0)
        stats['recebido_mes_atual'] = Decimal(stats.get('recebido_mes_atual') if stats.get('recebido_mes_atual') is not None else 0.0)
        stats['pago_mes_atual'] = Decimal(stats.get('pago_mes_atual') if stats.get('pago_mes_atual') is not None else 0.0)

    except Exception as e:
        flash(f"Erro ao carregar lançamentos financeiros: {e}", "danger")
        lancamentos_com_saldo = []
        stats = {
            'a_receber_total': Decimal('0.00'), 'a_pagar_total': Decimal('0.00'),
            'recebido_mes_atual': Decimal('0.00'), 'pago_mes_atual': Decimal('0.00')
        }
    
    return render_template('financeiro.html', 
                           lancamentos=lancamentos_com_saldo,
                           stats=stats,
                           filtro_status_atual=filtro_status,
                           filtro_tipo_atual=filtro_tipo)

@app.route('/financeiro/lancamento/novo', methods=['POST'])
def financeiro_lancamento_novo():
    try:
        data = {
            'descricao': request.form.get('descricao_lancamento'), 'tipo': request.form.get('tipo_lancamento'),
            'valor': float(request.form.get('valor_lancamento')), 'data_vencimento': request.form.get('data_vencimento_lancamento'),
            'status_pagamento': request.form.get('status_pagamento_lancamento', 'Pendente'),
            'forma_pagamento_efetiva': request.form.get('forma_pagamento_efetiva_lancamento'),
            'observacao': request.form.get('observacao_lancamento'),
            'data_pagamento': request.form.get('data_pagamento_lancamento') if request.form.get('data_pagamento_lancamento') and request.form.get('status_pagamento_lancamento', 'Pendente') == 'Pago' else None
        }
        if not all([data['descricao'], data['tipo'], data['valor'], data['data_vencimento']]):
            flash('Descrição, Tipo, Valor e Data de Vencimento são obrigatórios.', 'danger')
        elif data['valor'] <=0:
            flash('O valor do lançamento deve ser positivo.', 'danger')
        else:
            db_manager.add_lancamento_financeiro(data)
            flash('Lançamento financeiro adicionado com sucesso!', 'success')
    except ValueError:
        flash('Valor inválido para o lançamento.', 'danger')
    except Exception as e:
        flash(f'Erro ao adicionar lançamento: {str(e)}', 'danger')
    return redirect(url_for('financeiro_lista'))

@app.route('/financeiro/lancamento/update_status/<int:lancamento_id>', methods=['POST'])
def financeiro_lancamento_update_status(lancamento_id):
    try:
        novo_status = request.form.get('novo_status')
        data_pagamento = request.form.get('data_pagamento_lancamento')
        forma_pagamento_efetiva = request.form.get('forma_pagamento_efetiva_lancamento')

        if not novo_status:
            flash("Status não fornecido para atualização.", "warning")
            return redirect(url_for('financeiro_lista'))

        if novo_status == 'Pago' and not data_pagamento:
            data_pagamento = datetime.date.today().strftime('%Y-%m-%d')
        
        if novo_status != 'Pago':
            data_pagamento = None 
            forma_pagamento_efetiva = None

        if db_manager.update_status_lancamento(lancamento_id, novo_status, data_pagamento, forma_pagamento_efetiva):
            flash(f'Status do lançamento #{lancamento_id} atualizado para {novo_status}!', 'success')
        else:
            flash(f'Erro ao atualizar status do lançamento #{lancamento_id}.', 'danger')
    except Exception as e:
        flash(f'Erro ao atualizar status: {str(e)}', 'danger')
    return redirect(url_for('financeiro_lista'))

@app.route('/financeiro/lancamento/excluir/<int:lancamento_id>', methods=['POST'])
def financeiro_lancamento_excluir(lancamento_id):
    try:
        lancamento = db_manager.execute_query("SELECT venda_id FROM lancamentos_financeiros WHERE id = ?", (lancamento_id,), fetch_one=True)
        if lancamento and lancamento['venda_id']:
            venda = db_manager.get_venda_by_id(lancamento['venda_id'])
            if venda and venda['status'] == 'Concluída':
                flash('Não é possível excluir lançamentos de vendas concluídas. Cancele a venda primeiro.', 'warning')
                return redirect(url_for('financeiro_lista'))
        if db_manager.delete_lancamento_financeiro(lancamento_id):
            flash(f'Lançamento financeiro #{lancamento_id} excluído com sucesso!', 'success')
        else:
            flash(f'Erro ao excluir lançamento financeiro #{lancamento_id}.', 'danger')
    except Exception as e:
        flash(f'Erro ao excluir lançamento: {str(e)}', 'danger')
    return redirect(url_for('financeiro_lista'))

# Rota para servir imagens de produtos
@app.route('/uploads/product_images/<filename>')
def uploaded_product_image(filename):
    return send_from_directory(app.config['PRODUCT_IMAGE_UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found. Initializing...")
        try:
            db_manager.create_tables()
            print(f"Database {DB_NAME} and tables created.")
        except Exception as e:
            print(f"Error creating database tables: {e}")
    else:
        try:
            db_manager.create_tables()
            print(f"Database {DB_NAME} found, tables verified/created.")
        except Exception as e:
            print(f"Error verifying/creating tables in existing database: {e}")
    app.run(debug=True)
