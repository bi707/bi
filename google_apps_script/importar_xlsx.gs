// ============================================================
// CONFIGURAÇÕES — altere apenas aqui
// ============================================================
var CONFIG = {
  SOURCE_FOLDER_ID: '1dozTRcJLqlwOuoTg_qf4DfQHBZbIAGG-',
  DEST_SPREADSHEET_ID: '1NH4KFNxwoZ7e6JzFsHhNm7X8AeFlWU-ek2Af9tnnWt8',
  TRIGGER_HOUR: 6,
  TEMP_FILE_PREFIX: '_tmp_import_'
};

// ============================================================
// FUNÇÃO PRINCIPAL — chamada pelo trigger diário
// ============================================================
function importarXlsxParaSheet() {
  var folder = DriveApp.getFolderById(CONFIG.SOURCE_FOLDER_ID);
  var destSpreadsheet = SpreadsheetApp.openById(CONFIG.DEST_SPREADSHEET_ID);
  var props = PropertiesService.getScriptProperties();

  // Mapa persistente: fileId → nomeAba  (sobrevive entre execuções)
  var mapa = JSON.parse(props.getProperty('fileIdToTabName') || '{}');

  var processados = [];
  var erros = [];
  var tipos = [MimeType.MICROSOFT_EXCEL, MimeType.MICROSOFT_EXCEL_LEGACY];

  tipos.forEach(function(mime) {
    var files = folder.getFilesByType(mime);
    while (files.hasNext()) {
      var file = files.next();
      var fileId = file.getId();
      var nomeArquivo = file.getName().replace(/\.xlsx?$/i, '').substring(0, 100);

      var tempId = null;
      try {
        // Converte xlsx → Google Sheets temporariamente
        var tempFile = Drive.Files.copy(
          { title: CONFIG.TEMP_FILE_PREFIX + fileId, mimeType: MimeType.GOOGLE_SHEETS },
          fileId
        );
        tempId = tempFile.id;

        var sourceSheet = SpreadsheetApp.openById(tempId).getSheets()[0];
        var data = sourceSheet.getDataRange().getValues();

        // Resolve qual aba usar, usando fileId como chave estável
        var destSheet = resolverAba(destSpreadsheet, fileId, nomeArquivo, mapa);

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

  // Persiste o mapa atualizado
  props.setProperty('fileIdToTabName', JSON.stringify(mapa));

  var resumo = 'Importação concluída em ' + new Date().toLocaleString('pt-BR') + '\n'
    + 'Processados (' + processados.length + '): ' + processados.join(', ') + '\n'
    + (erros.length ? 'Erros (' + erros.length + '): ' + erros.join(' | ') : 'Sem erros.');

  Logger.log(resumo);
  return resumo;
}

// ============================================================
// Resolve a aba de destino pelo fileId (chave estável)
// Se o arquivo foi renomeado → renomeia a aba existente
// Se é novo → cria uma aba com o nome atual do arquivo
// ============================================================
function resolverAba(spreadsheet, fileId, nomeAtual, mapa) {
  var tabNameAnterior = mapa[fileId];

  if (tabNameAnterior) {
    var sheet = spreadsheet.getSheetByName(tabNameAnterior);
    if (sheet) {
      // Arquivo renomeado → atualiza o nome da aba automaticamente
      if (tabNameAnterior !== nomeAtual) {
        sheet.setName(nomeAtual);
        Logger.log('Aba renomeada: "' + tabNameAnterior + '" → "' + nomeAtual + '"');
        mapa[fileId] = nomeAtual;
      }
      return sheet;
    }
  }

  // Aba ainda não existe — cria e registra no mapa
  var novaAba = spreadsheet.getSheetByName(nomeAtual) || spreadsheet.insertSheet(nomeAtual);
  mapa[fileId] = nomeAtual;
  return novaAba;
}

// ============================================================
// TRIGGER — execute UMA VEZ manualmente para agendar
// ============================================================
function configurarTriggerDiario() {
  ScriptApp.getProjectTriggers()
    .filter(function(t) { return t.getHandlerFunction() === 'importarXlsxParaSheet'; })
    .forEach(function(t) { ScriptApp.deleteTrigger(t); });

  ScriptApp.newTrigger('importarXlsxParaSheet')
    .timeBased()
    .everyDays(1)
    .atHour(CONFIG.TRIGGER_HOUR)
    .create();

  Logger.log('Trigger diário configurado para ' + CONFIG.TRIGGER_HOUR + 'h.');
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

// ============================================================
// UTILITÁRIO — exibe o mapa fileId → nomeAba salvo
// ============================================================
function verMapa() {
  var mapa = PropertiesService.getScriptProperties().getProperty('fileIdToTabName');
  Logger.log(mapa || 'Mapa vazio.');
}
