/* Cérebro — app.js (external, CSP-compliant) */

// ── Helpers ─────────────────────────────────────────────────

function apiCall(url, options) {
    return fetch(url, options)
        .then(function (r) {
            if (!r.ok) {
                return r.json().then(function (e) {
                    throw new Error(e.detail || 'Erro ' + r.status);
                });
            }
            return r.json();
        });
}

// ── Sanitize + Markdown rendering ───────────────────────────

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdown(text) {
    // Escape HTML first to prevent XSS, then apply markdown formatting
    var safe = escapeHtml(text);
    return safe
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        .replace(/^• (.+)$/gm, '<li>$1</li>')
        .replace(/\n/g, '<br>');
}

document.addEventListener('DOMContentLoaded', function () {
    // Convert pre.output to rendered markdown
    document.querySelectorAll('pre.output').forEach(function (el) {
        var div = document.createElement('div');
        div.className = 'output-md';
        div.innerHTML = renderMarkdown(el.textContent);
        el.replaceWith(div);
    });

    // ── Auto-submit filter forms ────────────────────────────
    document.querySelectorAll('[data-autosubmit]').forEach(function (select) {
        select.addEventListener('change', function () {
            this.form.submit();
        });
    });

    // ── Concluir tarefa ─────────────────────────────────────
    document.querySelectorAll('[data-concluir]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-concluir');
            apiCall('/api/pendencias/' + id + '/concluir', { method: 'PUT' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao concluir: ' + err.message); });
        });
    });

    // ── Iniciar tarefa ──────────────────────────────────────
    document.querySelectorAll('[data-iniciar]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-iniciar');
            apiCall('/api/pendencias/' + id + '/iniciar', { method: 'PUT' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao iniciar: ' + err.message); });
        });
    });

    // ── Bloquear tarefa ────────────────────────────────────
    document.querySelectorAll('[data-bloquear]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-bloquear');
            apiCall('/api/pendencias/' + id + '/bloquear', { method: 'PUT' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao bloquear: ' + err.message); });
        });
    });

    // ── Cancelar tarefa ────────────────────────────────────
    document.querySelectorAll('[data-cancelar-pendencia]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-cancelar-pendencia');
            if (!confirm('Cancelar tarefa #' + id + '?')) return;
            apiCall('/api/pendencias/' + id + '/cancelar', { method: 'PUT' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao cancelar: ' + err.message); });
        });
    });

    // ── Excluir tarefa ──────────────────────────────────────
    document.querySelectorAll('[data-excluir-pendencia]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-excluir-pendencia');
            if (!confirm('Excluir tarefa #' + id + '?')) return;
            apiCall('/api/pendencias/' + id, { method: 'DELETE' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao excluir: ' + err.message); });
        });
    });

    // ── Modal de edição de pendência ──────────────────────────
    var modal = document.getElementById('modal-editar');
    if (modal) {
        var pendenciasData = [];
        try {
            var dataEl = document.getElementById('pendencias-data');
            if (dataEl) pendenciasData = JSON.parse(dataEl.textContent);
        } catch (e) { /* ignore */ }

        // Abrir modal
        document.querySelectorAll('[data-abrir-modal]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = parseInt(this.getAttribute('data-abrir-modal'));
                var p = pendenciasData.find(function (item) { return item.id === id; });
                if (!p) return;

                document.getElementById('modal-pendencia-id').value = p.id;
                document.getElementById('modal-edit-id').textContent = '#' + p.id;
                document.getElementById('modal-tarefa').value = p.tarefa;
                document.getElementById('modal-projeto').value = p.projeto;
                document.getElementById('modal-prioridade').value = p.prioridade;
                document.getElementById('modal-prazo').value = p.prazo;
                document.getElementById('modal-delegado').value = p.delegado_para;
                document.getElementById('modal-notas').value = p.notas;

                modal.showModal();
            });
        });

        // Fechar modal
        document.getElementById('modal-fechar').addEventListener('click', function () { modal.close(); });
        document.getElementById('modal-cancelar').addEventListener('click', function () { modal.close(); });
        modal.addEventListener('click', function (e) {
            if (e.target === modal) modal.close();
        });

        // Salvar via modal
        document.getElementById('modal-salvar').addEventListener('click', function () {
            var id = document.getElementById('modal-pendencia-id').value;
            var campos = {
                tarefa: document.getElementById('modal-tarefa').value,
                projeto: document.getElementById('modal-projeto').value,
                prioridade: parseInt(document.getElementById('modal-prioridade').value) || 3,
            };
            var prazo = document.getElementById('modal-prazo').value;
            if (prazo) campos.prazo = prazo;
            var delegado = document.getElementById('modal-delegado').value;
            if (delegado) campos.delegado_para = delegado;
            var notas = document.getElementById('modal-notas').value;
            if (notas) campos.notas = notas;

            apiCall('/api/pendencias/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(campos)
            }).then(function () { location.reload(); })
              .catch(function (err) { alert('Erro ao salvar: ' + err.message); });
        });
    }

    // ── Criar tarefa ────────────────────────────────────────
    var formTarefa = document.getElementById('form-criar-tarefa');
    if (formTarefa) {
        formTarefa.addEventListener('submit', function (e) {
            e.preventDefault();
            var form = e.target;
            var data = {
                tarefa: form.tarefa.value,
                projeto: form.projeto.value,
                prioridade: parseInt(form.prioridade.value),
                prazo: form.prazo.value || null,
                responsavel: form.responsavel.value || 'matheus'
            };
            apiCall('/api/pendencias', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(function () { location.reload(); })
              .catch(function (err) { alert('Erro ao criar: ' + err.message); });
        });
    }

    // ── Criar evento ────────────────────────────────────────
    var formEvento = document.getElementById('form-criar-evento');
    if (formEvento) {
        formEvento.addEventListener('submit', function (e) {
            e.preventDefault();
            var form = e.target;
            var data = {
                titulo: form.titulo.value,
                data: form.data.value,
                hora: form.hora.value || null,
                duracao_minutos: parseInt(form.duracao_minutos.value) || 60,
                projeto: form.projeto.value || null
            };
            apiCall('/api/eventos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(function () { location.reload(); })
              .catch(function (err) { alert('Erro ao criar evento: ' + err.message); });
        });
    }

    // ── Editar evento (toggle edit row) ────────────────────
    document.querySelectorAll('[data-editar-evento]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-editar-evento');
            document.getElementById('row-' + id).style.display = 'none';
            document.getElementById('edit-' + id).style.display = '';
        });
    });

    // ── Cancelar edição evento ──────────────────────────────
    document.querySelectorAll('[data-cancelar-evento]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-cancelar-evento');
            document.getElementById('row-' + id).style.display = '';
            document.getElementById('edit-' + id).style.display = 'none';
        });
    });

    // ── Salvar evento (PUT) ─────────────────────────────────
    document.querySelectorAll('[data-salvar-evento]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-salvar-evento');
            var editRow = document.getElementById('edit-' + id);
            var campos = {};
            editRow.querySelectorAll('[data-field]').forEach(function (input) {
                var field = input.getAttribute('data-field');
                var val = input.value;
                if (field === 'duracao_minutos') val = parseInt(val) || 60;
                if (val !== '') campos[field] = val;
            });
            apiCall('/api/eventos/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(campos)
            }).then(function () { location.reload(); })
              .catch(function (err) { alert('Erro ao salvar: ' + err.message); });
        });
    });

    // ── Excluir evento ──────────────────────────────────────
    document.querySelectorAll('[data-excluir-evento]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-excluir-evento');
            if (!confirm('Excluir evento #' + id + '?')) return;
            apiCall('/api/eventos/' + id, { method: 'DELETE' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao excluir: ' + err.message); });
        });
    });

    // ── Criar job ───────────────────────────────────────────
    var formJob = document.getElementById('form-criar-job');
    if (formJob) {
        formJob.addEventListener('submit', function (e) {
            e.preventDefault();
            var form = e.target;
            var data = {
                tipo: form.tipo.value,
                instrucoes: form.instrucoes.value,
                projeto: form.projeto.value || null
            };
            apiCall('/api/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(function () { location.reload(); })
              .catch(function (err) { alert('Erro ao criar job: ' + err.message); });
        });
    }

    // ── Criar lançamento ────────────────────────────────────
    var formLanc = document.getElementById('form-lancamento');
    if (formLanc) {
        formLanc.addEventListener('submit', function (e) {
            e.preventDefault();
            var form = e.target;
            var data = {
                tipo: form.tipo.value,
                valor: parseFloat(form.valor.value),
                descricao: form.descricao.value,
                categoria: form.categoria.value,
                projeto: form.projeto.value,
                data: form.data.value || null
            };
            apiCall('/api/lancamentos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(function () { location.reload(); })
              .catch(function (err) { alert('Erro ao registrar: ' + err.message); });
        });
    }

    // ── Excluir lançamento ──────────────────────────────────
    document.querySelectorAll('[data-excluir-lancamento]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-excluir-lancamento');
            if (!confirm('Excluir lançamento #' + id + '?')) return;
            apiCall('/api/lancamentos/' + id, { method: 'DELETE' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao excluir: ' + err.message); });
        });
    });

    // ── Pause / Resume toggle ───────────────────────────────
    var btnPause = document.getElementById('btn-pause');
    if (btnPause) {
        function applyPauseState(paused) {
            if (paused) {
                btnPause.textContent = '⏸ Pausado';
                btnPause.className = 'paused';
            } else {
                btnPause.textContent = '▶ Ativo';
                btnPause.className = 'active';
            }
        }

        fetch('/api/agente/status')
            .then(function (r) { return r.json(); })
            .then(function (d) { applyPauseState(d.paused); })
            .catch(function () {});

        btnPause.addEventListener('click', function () {
            apiCall('/api/agente/toggle', { method: 'POST' })
                .then(function (d) { applyPauseState(d.paused); })
                .catch(function () {});
        });
    }

    // ── Criar fato ──────────────────────────────────────────
    var formFato = document.getElementById('form-criar-fato');
    if (formFato) {
        formFato.addEventListener('submit', function (e) {
            e.preventDefault();
            var form = e.target;
            var data = {
                projeto: form.projeto.value,
                categoria: form.categoria.value,
                fato: form.fato.value
            };
            apiCall('/api/fatos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(function () { location.reload(); })
              .catch(function (err) { alert('Erro ao registrar fato: ' + err.message); });
        });
    }

    // ── Excluir fato ────────────────────────────────────────
    document.querySelectorAll('[data-excluir-fato]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-excluir-fato');
            if (!confirm('Desativar fato #' + id + '?')) return;
            apiCall('/api/fatos/' + id, { method: 'DELETE' })
                .then(function () { location.reload(); })
                .catch(function (err) { alert('Erro ao desativar: ' + err.message); });
        });
    });
});
