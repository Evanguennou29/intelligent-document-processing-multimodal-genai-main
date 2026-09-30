const samples = {
  invoice: {
    title: 'Facture', label: 'FACTURE / PDF', file: 'facture_nova.pdf',
    fields: [['N° FACTURE', 'INV-2026-042'], ['ÉMETTEUR', 'Atelier Nova'], ['DATE', '12.09.2026'], ['TOTAL TTC', '624,00 €']],
    data: { document_type: 'invoice', invoice_number: 'INV-2026-042', date: '2026-09-12', seller_name: 'Atelier Nova', subtotal: 520.00, tax_amount: 104.00, total_amount: 624.00, currency: 'EUR' },
    paper: `<div class="paper-eyebrow">ATELIER NOVA / DOCUMENT N° 042</div><div class="paper-brand">NOVA<span style="color:#809098"> / STUDIO</span></div><span class="paper-accent">PIÈCE COMPTABLE</span><div class="paper-title">FACTURE</div><div class="paper-row"><span>N°</span><b>INV-2026-042</b></div><div class="paper-row"><span>DATE</span><b>12 / 09 / 2026</b></div><div class="paper-row"><span>PRESTATION</span><b>IDENTITÉ VISUELLE</b></div><div class="paper-row"><span>SOUS-TOTAL</span><b>520,00 €</b></div><div class="paper-row"><span>TVA 20 %</span><b>104,00 €</b></div><div class="paper-total"><span>TOTAL TTC</span><strong>624,00 €</strong></div><div class="paper-bottom">RÉFÉRENCE : NV-2026-042 / PARIS</div>`
  },
  passport: {
    title: 'Passeport', label: 'PASSEPORT / JPEG', file: 'passeport_specimen.jpg',
    fields: [['NOM COMPLET', 'Camille Martin'], ['NATIONALITÉ', 'FRA'], ['N° DOCUMENT', 'SPC000421'], ['EXPIRATION', '2031-06-18']],
    data: { document_type: 'passport', full_name: 'Camille Martin', nationality: 'FRA', date_of_birth: '1998-04-14', passport_number: 'SPC000421', expiration_date: '2031-06-18', issuing_country: 'France' },
    paper: `<div class="passport-band">PASSEPORT <span style="font-size:10px;margin-left:10px">/ SPECIMEN</span></div><div class="paper-eyebrow">DOCUMENT FICTIF · NON VALABLE</div><div class="paper-title" style="font-size:21px;margin:8px 0 14px">IDENTITÉ</div><div class="passport-portrait">◯</div><div class="paper-row"><span>NOM</span><b>MARTIN</b></div><div class="paper-row"><span>PRÉNOM</span><b>CAMILLE</b></div><div class="paper-row"><span>NATIONALITÉ</span><b>FRA</b></div><div class="paper-row"><span>N°</span><b>SPC000421</b></div><div class="paper-row"><span>EXPIRATION</span><b>18.06.2031</b></div><div class="mrz">P&lt;FRAMARTIN&lt;&lt;CAMILLE&lt;&lt;&lt;&lt;&lt;&lt;<br>SPC0004217FRA9804145F3106182</div>`
  },
  prescription: {
    title: 'Ordonnance', label: 'ORDONNANCE / PNG', file: 'ordonnance_exemple.png',
    fields: [['PATIENT', 'Alex Petit'], ['PRESCRIPTEUR', 'Dr. Moreau'], ['DATE', '2026-09-15'], ['LIGNES', '2 médicaments']],
    data: { document_type: 'prescription', patient_name: 'Alex Petit', doctor_name: 'Dr. Moreau', date: '2026-09-15', items: [{ drug_name: 'Médicament A', dosage: 'Exemple fictif' }, { drug_name: 'Médicament B', dosage: 'Exemple fictif' }] },
    paper: `<div class="paper-eyebrow">CABINET MÉDICAL / SPÉCIMEN</div><div class="paper-brand">DR. MOREAU</div><span class="paper-accent">DOCUMENT FICTIF</span><div class="paper-title" style="font-size:21px">ORDONNANCE</div><div class="paper-row"><span>PATIENT</span><b>ALEX PETIT</b></div><div class="paper-row"><span>DATE</span><b>15 / 09 / 2026</b></div><div class="paper-line"></div><div class="paper-row"><span>01</span><b>MÉDICAMENT A</b></div><div class="paper-line short"></div><div class="paper-row"><span>02</span><b>MÉDICAMENT B</b></div><div class="paper-line tiny"></div><div class="paper-bottom">EXEMPLE VISUEL SANS VALEUR MÉDICALE</div>`
  },
  certificate: {
    title: 'Certificat', label: 'CERTIFICAT / PDF', file: 'certificat_exemple.pdf',
    fields: [['TITRE', 'Attestation'], ['TITULAIRE', 'Noa Bernard'], ['ÉMISSION', '2026-09-10'], ['AUTORITÉ', 'Ville de Lyon']],
    data: { document_type: 'certificate', title: 'Attestation', person_name: 'Noa Bernard', issue_date: '2026-09-10', issuing_authority: 'Ville de Lyon', details: 'Document d’exemple' },
    paper: `<div class="paper-eyebrow">VILLE DE LYON / SPÉCIMEN</div><div class="paper-brand">LYON <span style="font-weight:400">/ SERVICE</span></div><span class="paper-accent">PIÈCE ADMINISTRATIVE</span><div class="paper-title" style="font-size:21px">ATTESTATION</div><div class="paper-line"></div><div class="paper-line short"></div><div class="paper-row"><span>TITULAIRE</span><b>NOA BERNARD</b></div><div class="paper-row"><span>ÉMISSION</span><b>10 / 09 / 2026</b></div><div class="paper-line"></div><div class="paper-line tiny"></div><div class="paper-bottom">DOCUMENT D'EXEMPLE · AUCUNE VALEUR OFFICIELLE</div>`
  }
};

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const state = { doc: 'invoice', engine: 'vertex', running: false, timers: [], typeTimer: null };
const stageNames = ['IMPORT DU FICHIER', 'LECTURE OCR', 'ROUTAGE DU DOCUMENT', 'EXTRACTION STRUCTURÉE', 'VALIDATION DU SCHÉMA'];
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);

function payload() {
  const sample = samples[state.doc];
  return { ...sample.data, _meta: { provider: state.engine, source_file: sample.file, document_type: sample.data.document_type, warnings: [] } };
}

function highlightedJson(value) {
  return escapeHtml(value).replace(/(&quot;[^&]*?&quot;)(\s*:)?|(-?\d+(?:\.\d+)?)/g, (match, quoted, colon, number) => {
    if (number) return `<span class="code-number">${number}</span>`;
    return colon ? `<span class="code-key">${quoted}</span>${colon}` : `<span class="code-string">${quoted}</span>`;
  });
}

function clearTimers() {
  state.timers.forEach(clearTimeout);
  state.timers = [];
  if (state.typeTimer) clearInterval(state.typeTimer);
  state.typeTimer = null;
}

function showSample() {
  const sample = samples[state.doc];
  $('#paper').innerHTML = sample.paper;
  $('#scanTag').textContent = sample.label;
  $('#resultTitle').textContent = sample.title;
  $('#fieldGrid').innerHTML = sample.fields.map(([key, value], index) => `<div class="field" style="animation-delay:${index * 80}ms"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
  $('#jsonOutput').innerHTML = highlightedJson(JSON.stringify(payload(), null, 2));
  $('#engineCaption').textContent = state.engine === 'vertex' ? 'Cloud · Gemini Vision' : 'Local · modèle de vision';
}

function resetSequence() {
  clearTimers();
  state.running = false;
  $('#scannerStage').classList.remove('scanning');
  $('#benchStatus').textContent = 'PRÊT À EXPLORER';
  $('#scanMessage').textContent = 'EN ATTENTE DE SÉQUENCE';
  $('#runLabel').textContent = 'LANCER LA SÉQUENCE';
  $('#runButton').disabled = false;
  $$('#stageLabels span').forEach(span => span.classList.remove('active'));
  showSample();
}

function typeOutput() {
  const json = JSON.stringify(payload(), null, 2);
  const target = $('#jsonOutput');
  let cursor = 0;
  target.textContent = '';
  state.typeTimer = setInterval(() => {
    cursor = Math.min(cursor + 12, json.length);
    target.textContent = json.slice(0, cursor);
    target.parentElement.scrollTop = target.parentElement.scrollHeight;
    if (cursor === json.length) {
      clearInterval(state.typeTimer);
      state.typeTimer = null;
      target.innerHTML = highlightedJson(json);
    }
  }, 16);
}

function runSequence() {
  if (state.running) return;
  clearTimers();
  state.running = true;
  $('#runButton').disabled = true;
  $('#runLabel').textContent = 'ANALYSE EN COURS';
  $('#benchStatus').textContent = 'TRAITEMENT ACTIF';
  $('#jsonOutput').textContent = '{\n  ...\n}';
  $$('#stageLabels span').forEach(span => span.classList.remove('active'));
  stageNames.forEach((name, index) => {
    state.timers.push(setTimeout(() => {
      $('#benchStatus').textContent = name;
      $('#scanMessage').textContent = name;
      $$('#stageLabels span')[index].classList.add('active');
      $('#scannerStage').classList.toggle('scanning', index === 1 || index === 3);
      if (index === 3) typeOutput();
      if (index === 4) {
        state.timers.push(setTimeout(() => {
          $('#scannerStage').classList.remove('scanning');
          $('#benchStatus').textContent = 'DOCUMENT STRUCTURÉ';
          $('#scanMessage').textContent = 'EXTRACTION TERMINÉE';
          $('#runLabel').textContent = 'REJOUER LA SÉQUENCE';
          $('#runButton').disabled = false;
          state.running = false;
          if (state.typeTimer) { clearInterval(state.typeTimer); state.typeTimer = null; }
          $('#jsonOutput').innerHTML = highlightedJson(JSON.stringify(payload(), null, 2));
        }, 650));
      }
    }, index * 710));
  });
}

$$('.doc-choice').forEach(button => button.addEventListener('click', () => {
  state.doc = button.dataset.doc;
  $$('.doc-choice').forEach(choice => { const active = choice === button; choice.classList.toggle('active', active); choice.setAttribute('aria-pressed', String(active)); });
  resetSequence();
}));
$$('.engine').forEach(button => button.addEventListener('click', () => {
  state.engine = button.dataset.engine;
  $$('.engine').forEach(choice => { const active = choice === button; choice.classList.toggle('active', active); choice.setAttribute('aria-pressed', String(active)); });
  resetSequence();
}));
$('#runButton').addEventListener('click', runSequence);
$('#resetButton').addEventListener('click', resetSequence);
showSample();

const revealObserver = new IntersectionObserver(entries => entries.forEach(entry => {
  if (entry.isIntersecting) { entry.target.classList.add('visible'); revealObserver.unobserve(entry.target); }
}), { threshold: .08 });
$$('.reveal').forEach(section => revealObserver.observe(section));

if (matchMedia('(pointer:fine)').matches && !matchMedia('(prefers-reduced-motion:reduce)').matches) {
  const glow = $('.cursor-glow');
  window.addEventListener('pointermove', event => { glow.style.left = `${event.clientX}px`; glow.style.top = `${event.clientY}px`; glow.style.opacity = '1'; }, { passive: true });
  window.addEventListener('pointerleave', () => { glow.style.opacity = '0'; });
}
