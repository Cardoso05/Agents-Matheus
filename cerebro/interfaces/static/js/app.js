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

// ── Markdown rendering ──────────────────────────────────────

function renderMarkdown(text) {
    return text
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
});
