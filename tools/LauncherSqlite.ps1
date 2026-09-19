# Minimal UTF-8 SQLite access through the Windows system library.
# Connections never create a missing database; read-only access is the default.
if (-not ('Ck3LauncherDatabase' -as [type])) {
	Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public sealed class Ck3LauncherDatabase : IDisposable {
    private IntPtr handle;
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_open_v2(byte[] name, out IntPtr db, int flags, IntPtr vfs);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_close_v2(IntPtr db);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_busy_timeout(IntPtr db, int milliseconds);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr sqlite3_errmsg(IntPtr db);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_prepare_v2(IntPtr db, byte[] sql, int length, out IntPtr statement, IntPtr tail);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_step(IntPtr statement);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_finalize(IntPtr statement);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_column_count(IntPtr statement);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr sqlite3_column_name(IntPtr statement, int column);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr sqlite3_column_text(IntPtr statement, int column);
    [DllImport("winsqlite3.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int sqlite3_column_type(IntPtr statement, int column);

    private static byte[] Utf8(string value) { return Encoding.UTF8.GetBytes(value + "\0"); }
    private static string Text(IntPtr pointer) {
        if (pointer == IntPtr.Zero) return null;
        int length = 0;
        while (Marshal.ReadByte(pointer, length) != 0) length++;
        byte[] bytes = new byte[length];
        Marshal.Copy(pointer, bytes, 0, length);
        return Encoding.UTF8.GetString(bytes);
    }
    public Ck3LauncherDatabase(string path, bool writable) {
        int result = sqlite3_open_v2(Utf8(path), out handle, writable ? 2 : 1, IntPtr.Zero);
        if (result != 0) {
            string error = Text(sqlite3_errmsg(handle));
            Dispose();
            throw new InvalidOperationException(error);
        }
        sqlite3_busy_timeout(handle, 3000);
    }
    public List<Dictionary<string,string>> Query(string sql) {
        IntPtr statement;
        if (sqlite3_prepare_v2(handle, Utf8(sql), -1, out statement, IntPtr.Zero) != 0)
            throw new InvalidOperationException(Text(sqlite3_errmsg(handle)));
        var rows = new List<Dictionary<string,string>>();
        try {
            int result;
            while ((result = sqlite3_step(statement)) == 100) {
                var row = new Dictionary<string,string>(StringComparer.Ordinal);
                for (int i = 0; i < sqlite3_column_count(statement); i++)
                    row.Add(Text(sqlite3_column_name(statement, i)), sqlite3_column_type(statement, i) == 5 ? null : Text(sqlite3_column_text(statement, i)));
                rows.Add(row);
            }
            if (result != 101) throw new InvalidOperationException(Text(sqlite3_errmsg(handle)));
            return rows;
        } finally { sqlite3_finalize(statement); }
    }
    public void Execute(string sql) { Query(sql); }
    public void Dispose() {
        if (handle != IntPtr.Zero) { sqlite3_close_v2(handle); handle = IntPtr.Zero; }
    }
}
'@
}
