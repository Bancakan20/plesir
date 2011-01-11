package org.bancakan.plesir.ui
{
	import flash.events.Event;
	import flash.events.MouseEvent;
	
	import mx.events.FlexEvent;
	
	import org.bancakan.plesir.Client;
	
	import spark.components.Button;
	import spark.components.Label;
	import spark.components.TextArea;
	import spark.components.WindowedApplication;
	
	[Bindable]
	public class PlesirTesterApplication extends WindowedApplication
	{
		public var startButton:Button = new Button();
		public var plesirClient:Client = new Client();
		public var txtDisplay:TextArea = new TextArea();
		public var lblConnect:Label = new Label();
		public function PlesirTesterApplication()
		{
			super();
			this.addEventListener(FlexEvent.CREATION_COMPLETE, this.creationCompleteHandler);
		}
		
		private function creationCompleteHandler(event:FlexEvent):void
		{
			startButton.addEventListener(MouseEvent.CLICK, startHandler);
			plesirClient.addEventListener(Event.CONNECT, connectHandler);
			plesirClient.addEventListener(Client.DATA_ARRIVED, receiveHandler);
		}
		
		private function startHandler(event:MouseEvent):void
		{
			this.plesirClient.connect("192.168.1.107", 50000);
		}
		
		private function receiveHandler(event:Event):void
		{
			var last_item:Array;
			last_item = plesirClient.last_item;
			for ( var i:int = 0; i < last_item.length; ++i )
			{
				this.txtDisplay.text += i.toString() + "-" + last_item[i].title+"\n";
			}
		}
		
		private function connectHandler(event:Event):void
		{
			this.lblConnect.text = "Connected";
		}
	}
}