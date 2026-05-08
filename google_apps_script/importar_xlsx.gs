// ============================================================
// CONFIGURAÇÕES — altere apenas aqui
// ============================================================
var CONFIG = {
  SOURCE_FOLDER_ID: '1dozTRcJLqlwOuoTg_qf4DfQHBZbIAGG-',
  DEST_SPREADSHEET_ID: '1NH4KFNxwoZ7e6JzFsHhNm7X8AeFlWU-ek2Af9tnnWt8',
  TRIGGER_HOUR: 6,           // hora do disparo diário (0–23, fuso do projeto)
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
      var tabName = file.getName()
        .replace(/\.xlsx?$/i, '')
        .substring(0, 100); // limite de caracteres no nome da aba

      var tempId = null;
      try {
        // Converte o xlsx para Google Sheets temporariamente
        var tempResource = { title: CONFIG.TEMP_FILE_PREFIX + file.getId(), mimeType: MimeType.GOOGLE_SHEETS };
        var tempFile = Drive.Files.copy(tempResource, file.getId());
        tempId = tempFile.id;

        // Lê apenas a primeira aba do arquivo convertido
        var tempSpreadsheet = SpreadsheetApp.openById(tempId);
        var sourceSheet = tempSpreadsheet.getSheets()[0];
        var data = sourceSheet.getDataRange().getValues();

        // Localiza ou cria a aba de destino com o nome do arquivo
        var destSheet = destSpreadsheet.getSheetByName(tabName);
        if (!destSheet) {
          destSheet = destSpreadsheet.insertSheet(tabName);
        } else {
          destSheet.clearContents();
        }

        // Grava os dados
        if (data.length > 0 && data[0].length > 0) {
          destSheet.getRange(1, 1, data.length, data[0].length).setValues(data);
        }

        processados.push(tabName);

      } catch (e) {
        erros.push(tabName + ': ' + e.message);
        Logger.log('ERRO em ' + tabName + ' — ' + e.message);

      } finally {
        // Sempre remove o arquivo temporário, mesmo em caso de erro
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
// TRIGGER — execute UMA VEZ manualmente para agendar
// ============================================================
function configurarTriggerDiario() {
  // Remove triggers anteriores da mesma função para evitar duplicatas
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
// UTILITÁRIO — limpa eventuais arquivos temporários órfãos
// ============================================================
function limparTemporarios() {
  var files = DriveApp.searchFiles('title contains "' + CONFIG.TEMP_FILE_PREFIX + '"');
  var count = 0;
  while (files.hasNext()) {
    files.next().setTrashed(true);
    count++;
  }
  Logger.log('Temporários removidos: ' + count);
}
