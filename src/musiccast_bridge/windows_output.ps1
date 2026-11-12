# Bundled Core Audio helper. JSON arrives on stdin; no user text is evaluated.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    $request = [Console]::In.ReadToEnd() | ConvertFrom-Json
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace MusicCastBridge {
    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class Enumerator {}
    [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IDevices {
        void EnumAudioEndpoints(int flow, uint mask, out ICollection devices);
        void GetDefaultAudioEndpoint(int flow, int role, out IDevice device);
    }
    // IID_IMMDeviceCollection from the Microsoft Windows SDK (mmdeviceapi.h).
    [ComImport, Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface ICollection { void GetCount(out uint count); void Item(uint index, out IDevice device); }
    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IDevice {
        void Activate(ref Guid iid, uint context, IntPtr parameters, out IntPtr value);
        void OpenPropertyStore(int mode, out IProperties store);
        void GetId(out IntPtr id);
        void GetState(out uint state);
    }
    [StructLayout(LayoutKind.Sequential)] struct PropertyKey { public Guid format; public uint id; }
    [StructLayout(LayoutKind.Explicit, Size=24)] struct Variant {
        [FieldOffset(0)] public ushort type;
        [FieldOffset(8)] public IntPtr text;
    }
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IProperties {
        void GetCount(out uint count); void GetAt(uint index, out PropertyKey key);
        void GetValue(ref PropertyKey key, out Variant value);
    }
    [ComImport, Guid("870AF99C-171D-4F9E-AF0D-E63DF40C2BC9")] class Policy {}
    // IPolicyConfig: method order is the Windows COM ABI, not a public SDK API.
    [ComImport, Guid("F8679F50-850A-41CF-9C72-430F290290C8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPolicy {
        void GetMixFormat(); void GetDeviceFormat(); void ResetDeviceFormat();
        void SetDeviceFormat(); void GetProcessingPeriod(); void SetProcessingPeriod();
        void GetShareMode(); void SetShareMode(); void GetPropertyValue(); void SetPropertyValue();
        void SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string endpoint, int role);
    }
    public class Endpoint { public string id; public string name; }
    public class State {
        public List<Endpoint> devices = new List<Endpoint>();
        public Dictionary<string,string> defaults = new Dictionary<string,string>();
    }
    public static class Audio {
        [DllImport("ole32.dll")] static extern int PropVariantClear(ref Variant value);
        static string Id(IDevice device) {
            IntPtr value; device.GetId(out value);
            try { return Marshal.PtrToStringUni(value); } finally { Marshal.FreeCoTaskMem(value); }
        }
        public static State Read() {
            var state = new State(); var enumerator = (IDevices)new Enumerator();
            ICollection devices = null;
            try {
                enumerator.EnumAudioEndpoints(0, 1, out devices);
                uint count; devices.GetCount(out count);
                for (uint i=0; i<count; i++) {
                    IDevice device; devices.Item(i, out device); IProperties properties = null;
                    try {
                        device.OpenPropertyStore(0, out properties);
                        var key = new PropertyKey { format = new Guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"), id = 14 };
                        Variant value; properties.GetValue(ref key, out value);
                        try { state.devices.Add(new Endpoint { id=Id(device), name=value.type==31 ? Marshal.PtrToStringUni(value.text) : Id(device) }); }
                        finally { PropVariantClear(ref value); }
                    } finally {
                        if(properties!=null) Marshal.ReleaseComObject(properties);
                        Marshal.ReleaseComObject(device);
                    }
                }
                for(int role=0;role<2;role++) {
                    IDevice device;
                    try { enumerator.GetDefaultAudioEndpoint(0, role, out device); }
                    catch(COMException) { continue; }
                    try { state.defaults[role.ToString()]=Id(device); } finally { Marshal.ReleaseComObject(device); }
                }
                return state;
            } finally {
                if(devices!=null) Marshal.ReleaseComObject(devices);
                Marshal.ReleaseComObject(enumerator);
            }
        }
        public static void Select(string endpoint, int[] roles) {
            if(!Read().devices.Exists(d => d.id==endpoint)) throw new ArgumentException("Inactive endpoint");
            foreach(int role in roles) if(role<0 || role>1) throw new ArgumentException("Invalid role");
            var policy=(IPolicy)new Policy();
            try { foreach(int role in roles) policy.SetDefaultEndpoint(endpoint, role); }
            finally { Marshal.ReleaseComObject(policy); }
        }
    }
}
'@
    if ($request.operation -eq 'select') {
        [MusicCastBridge.Audio]::Select([string]$request.endpoint, [int[]]$request.roles)
    } elseif ($request.operation -ne 'list') {
        throw 'Unknown operation'
    }
    [MusicCastBridge.Audio]::Read() | ConvertTo-Json -Depth 5 -Compress
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
