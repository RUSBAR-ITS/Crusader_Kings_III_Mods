# Preserve caller-selected encoding/BOM, but make generated text use LF.
# Keep hashes calculated by callers byte-exact: normalize BEFORE writing.
if (-not ('RepositoryText' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;

public static class RepositoryText {
    public static string Normalize(string text) {
        return text == null ? null : text.Replace("\r\n", "\n").Replace("\r", "\n");
    }
    public static void WriteAllText(string path, string text, Encoding encoding) {
        File.WriteAllText(path, Normalize(text), encoding);
    }
    public static void WriteAllText(string path, string text) {
        WriteAllText(path, text, new UTF8Encoding(false));
    }
    public static void WriteAllLines(string path, IEnumerable<string> lines, Encoding encoding) {
        using (var writer = new StreamWriter(path, false, encoding)) {
            writer.NewLine = "\n";
            foreach (var line in lines) writer.WriteLine(Normalize(line));
        }
    }
}
'@
}
