// ============================================================
// CONFIGURAÇÕES — altere apenas aqui
// ============================================================
var CONFIG = {
  SOURCE_FOLDER_ID: '1dozTRcJLqlwOuoTg_qf4DfQHBZbIAGG-',
  DEST_SPREADSHEET_ID: '1NH4KFNxwoZ7e6JzFsHhNm7X8AeFlWU-ek2Af9tnnWt8',
  TRIGGER_HOURS: [9, 13, 17],  // horários de execução diária
  TEMP_FILE_PREFIX: '_tmp_import_'
};

// ============================================================
// FUNÇÃO PRINCIPAL — chamada pelo trigger diário
// ============================================================
function importarXlsxParaSheet() {
  var folder = DriveApp.getFolderById(CONFIG.SOURCE_FOLDER_ID);
  var destSpreadsheet = SpreadsheetApp.openById(CONFIG.DEST_SPREADSHEET_ID);
  var processados = [];
  var erros = [];
  var tipos = [MimeType.MICROSOFT_EXCEL, MimeType.MICROSOFT_EXCEL_LEGACY];

  tipos.forEach(function(mime) {
    var files = folder.getFilesByType(mime);
    while (files.hasNext()) {
      var file = files.next();
      var nomeArquivo = file.getName().replace(/\.xlsx?$/i, '').substring(0, 100);

      var tempId = null;
      try {
        var tempFile = Drive.Files.copy(
          { title: CONFIG.TEMP_FILE_PREFIX + file.getId(), mimeType: MimeType.GOOGLE_SHEETS },
          file.getId()
        );
        tempId = tempFile.id;

        var sourceSheet = SpreadsheetApp.openById(tempId).getSheets()[0];
        var data = sourceSheet.getDataRange().getValues();

        var destSheet = resolverAbaPorNome(destSpreadsheet, nomeArquivo);
        destSheet.clearContents();
        if (data.length > 0 && data[0].length > 0) {
          destSheet.getRange(1, 1, data.length, data[0].length).setValues(data);
        }

        processados.push(nomeArquivo);

      } catch (e) {
        erros.push(nomeArquivo + ': ' + e.message);
        Logger.log('ERRO em ' + nomeArquivo + ' — ' + e.message);

      } finally {
        if (tempId) {
          try { DriveApp.getFileById(tempId).setTrashed(true); } catch (_) {}
        }
      }
    }
  });

  var resumo = 'Importação concluída em ' + new Date().toLocaleString('pt-BR') + '\n'
    + 'Processados (' + processados.length + '): ' + processados.join(', ') + '\n'
    + (erros.length ? 'Erros (' + erros.length + '): ' + erros.join(' | ') : 'Sem erros.');

  Logger.log(resumo);
  return resumo;
}

// ============================================================
// Localiza a aba pelo nome normalizado para evitar duplicatas
// por pequenas variações (acentos, maiúsculas, espaços extras).
// Se encontrar → usa a aba existente (e corrige o nome se mudou).
// Se não encontrar → cria uma aba nova.
// ============================================================
function resolverAbaPorNome(spreadsheet, nomeArquivo) {
  var chave = normalizar(nomeArquivo);
  var sheets = spreadsheet.getSheets();

  for (var i = 0; i < sheets.length; i++) {
    if (normalizar(sheets[i].getName()) === chave) {
      // Corrige o nome da aba caso tenha mudado ligeiramente
      if (sheets[i].getName() !== nomeArquivo) {
        Logger.log('Nome corrigido: "' + sheets[i].getName() + '" → "' + nomeArquivo + '"');
        sheets[i].setName(nomeArquivo);
      }
      return sheets[i];
    }
  }

  return spreadsheet.insertSheet(nomeArquivo);
}

// Remove acentos, converte para minúsculas e colapsa espaços
function normalizar(str) {
  return str
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '') // remove acentos
    .replace(/\s+/g, ' ')
    .trim();
}

// ============================================================
// TRIGGER — execute UMA VEZ manualmente para agendar
// ============================================================
function configurarTriggerDiario() {
  // Remove todos os triggers anteriores da função para evitar duplicatas
  ScriptApp.getProjectTriggers()
    .filter(function(t) { return t.getHandlerFunction() === 'importarXlsxParaSheet'; })
    .forEach(function(t) { ScriptApp.deleteTrigger(t); });

  // Cria um trigger para cada horário configurado
  CONFIG.TRIGGER_HOURS.forEach(function(hora) {
    ScriptApp.newTrigger('importarXlsxParaSheet')
      .timeBased()
      .everyDays(1)
      .atHour(hora)
      .create();
  });

  Logger.log('Triggers configurados para: ' + CONFIG.TRIGGER_HOURS.join('h, ') + 'h.');
}

// ============================================================
// UTILITÁRIO — limpa arquivos temporários órfãos
// ============================================================
function limparTemporarios() {
  var files = DriveApp.searchFiles('title contains "' + CONFIG.TEMP_FILE_PREFIX + '"');
  var count = 0;
  while (files.hasNext()) { files.next().setTrashed(true); count++; }
  Logger.log('Temporários removidos: ' + count);
}
