package org.bancakan.plesir
{
	import com.adobe.serialization.json.JSON;
	
	import flash.events.Event;
	import flash.events.EventDispatcher;
	import flash.events.IOErrorEvent;
	import flash.events.ProgressEvent;
	import flash.events.SecurityErrorEvent;
	import flash.net.Socket;
	import flash.utils.ByteArray;
	
	import org.bancakan.plesir.definition.PlaceData;
	
	public class Client extends EventDispatcher
	{
		private var socket:Socket;
		private var hostname:String;
		private var port:uint;
		private var _last_item:*;
		
		public static const DATA_ARRIVED:String = "dataArrived"
		
		public function Client()
		{
			this.socket = new Socket();
			this.socket.addEventListener(Event.CONNECT, dispatchEvent);
			this.socket.addEventListener(Event.CLOSE, dispatchEvent);
			this.socket.addEventListener(IOErrorEvent.IO_ERROR, dispatchEvent);
			this.socket.addEventListener(ProgressEvent.SOCKET_DATA, this.on_data_arrived);
			
		}
		
		public function connect(hostname:String, port:int=50000):void
		{
			this.socket.connect(hostname, port);
		}
		
		public function close():void
		{
			this.socket.close();
		}
		
		private function on_data_arrived(e:Event):void
		{
			var len:int   = this.socket.readInt();
			var json_data:ByteArray = new ByteArray();
			this.socket.readBytes(json_data, 0, len);
			var jsonobj:* = JSON.decode(json_data.toString());
			_last_item = jsonobj;
			this.dispatchEvent( new Event(Client.DATA_ARRIVED));
		}
		
		public function get last_item():*
		{
			return this._last_item;
		}
		
	}
}