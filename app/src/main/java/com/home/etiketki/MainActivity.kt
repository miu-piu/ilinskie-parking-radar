package com.home.etiketki

import android.Manifest
import android.app.*
import android.bluetooth.*
import android.content.pm.PackageManager
import android.graphics.*
import android.os.*
import android.text.*
import android.widget.*
import java.io.ByteArrayOutputStream
import java.util.UUID
import kotlin.concurrent.thread

class MainActivity:Activity(){
 private val items=listOf(
 "Электроника|Кабели · зарядки · переходники","Кабели|USB-C · HDMI · Lightning","Зарядки|Блоки питания · адаптеры","Компьютеры|Мыши · клавиатуры","Телефоны|Чехлы · стекла","Батарейки|AA · AAA · аккумуляторы",
 "Инструменты|Отвёртки · ключи · биты","Крепёж|Винты · гайки · шайбы","Ремонт|Клей · ленты · герметики","Умный дом|Датчики · реле","Документы|Договоры · справки","Гарантии|Чеки · инструкции",
 "Канцелярия|Ручки · карандаши","Бумага|Блокноты · конверты","Фото|Альбомы · рамки","Праздники|Декор · свечи","Новый год|Игрушки · гирлянды","Подарки|Упаковка · открытки",
 "Хобби|Материалы · принадлежности","Шитьё|Нитки · иглы","Кухня|Принадлежности","Выпечка|Формы · насадки","Специи|Приправы · смеси","Запасы|Крупы · макароны",
 "Контейнеры|Крышки · банки","Уборка|Салфетки · губки","Бытовая химия|Чистящие средства","Стирка|Средства · мешки","Косметика|Уход · маски","Уход за волосами|Шампуни · маски",
 "Аптечка — общая|Перевязочные материалы","Лекарства — мои|Препараты · витамины","Лекарства — мужа|Препараты · витамины","Лекарства — детские|Препараты · термометр",
 "Одежда — моя|Сезонные вещи","Одежда — мужа|Сезонные вещи","Обувь — моя|Сезонная обувь","Обувь — мужа|Сезонная обувь","Аксессуары — мои|Сумки · ремни","Аксессуары — мужа|Ремни · часы",
 "Детская одежда|Боди · слипы","Детская обувь|Ботинки · сапоги","Детские игрушки|Игры · фигурки","Детское творчество|Краски · бумага","Детский уход|Подгузники · кремы",
 "Собака|Всё для собаки","Автомобиль|Автоаксессуары","Путешествия|Чемоданы","Сезонное|Временное хранение","Запас|Резервные вещи"
 ).map{val a=it.split("|",limit=2);Pair(a[0],a[1])}
 private val queue=mutableListOf<Pair<String,String>>()
 private lateinit var catalog:LinearLayout
 private lateinit var status:TextView
 private lateinit var counter:TextView
 private lateinit var logView:TextView
 private val events=mutableListOf<String>()
 private var printer:BluetoothDevice?=null
 @Volatile private var diagnosticBusy=false
 private val ui=Handler(Looper.getMainLooper())
 override fun onCreate(savedInstanceState:Bundle?){
  super.onCreate(savedInstanceState)
  window.statusBarColor=Color.rgb(18,20,24)
  window.navigationBarColor=Color.rgb(18,20,24)
  val root=LinearLayout(this).apply{orientation=1;setBackgroundColor(Color.rgb(18,20,24));setPadding(16,16,16,12)}
  setContentView(root)
  root.addView(TextView(this).apply{text="Этикетки";textSize=26f;setTextColor(Color.WHITE);setTypeface(null,Typeface.BOLD)})
  root.addView(TextView(this).apply{text="75 × 120 мм · 3 этикетки на лист";textSize=13f;setTextColor(Color.LTGRAY)})
  status=TextView(this).apply{text="Принтер не выбран";setTextColor(Color.rgb(117,216,211));setPadding(0,12,0,8)};root.addView(status)
  button(root,"Выбрать принтер"){choosePrinter()}
  val search=EditText(this).apply{hint="Поиск по категориям";setSingleLine(true);setTextColor(Color.WHITE);setHintTextColor(Color.GRAY);setPadding(12,8,12,8)}
  root.addView(search)
  val scroll=ScrollView(this).apply{isFillViewport=false}
  catalog=LinearLayout(this).apply{orientation=1}
  scroll.addView(catalog)
  root.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
  counter=TextView(this).apply{setTextColor(Color.WHITE);setPadding(0,8,0,8);maxLines=2};root.addView(counter)
  val actions=LinearLayout(this).apply{orientation=0}
  root.addView(actions)
  button(actions,"+ Своя"){edit("","")}
  button(actions,"Очистить"){queue.clear();updateCount();log("Очередь очищена")}
  button(actions,"Тест"){print(true)}
  button(root,"Напечатать очередь"){print(false)}
  val logHeader=LinearLayout(this).apply{orientation=0};root.addView(logHeader)
  button(logHeader,"Диагностика"){showDiagnostics()}
  button(logHeader,"Журнал"){showLog()}
  button(logHeader,"Копировать лог"){val cm=getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager;cm.setPrimaryClip(android.content.ClipData.newPlainText("Этикетки — лог",events.joinToString("\\n")));toast("Лог скопирован")}
  logView=TextView(this).apply{setTextColor(Color.LTGRAY);textSize=11f;maxLines=2};root.addView(logView)
  log("Приложение запущено")
  search.addTextChangedListener(object:TextWatcher{
   override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int){}
   override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int){render(s.toString())}
   override fun afterTextChanged(s:Editable?){}
  })
  render("");updateCount()
  if(Build.VERSION.SDK_INT>=31&&checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED)
   requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT),1)
 }
 private fun button(parent:LinearLayout,label:String,fn:()->Unit){
  val b=Button(this).apply{text=label;isAllCaps=false;textSize=13f;setTextColor(Color.WHITE);setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(49,57,68)));setOnClickListener{fn()}}
  parent.addView(b,LinearLayout.LayoutParams(0,-2,1f).takeIf{parent.orientation==0}?:LinearLayout.LayoutParams(-1,-2))
 }
 private fun render(q:String){
  catalog.removeAllViews()
  items.filter{it.first.contains(q,true)||it.second.contains(q,true)}.forEach{(a,b)->
   val card=LinearLayout(this).apply{orientation=1;setPadding(18,12,18,12);setBackgroundColor(Color.rgb(32,36,43));setOnClickListener{edit(a,b)}}
   card.addView(TextView(this).apply{text=a;textSize=16f;setTextColor(Color.WHITE);setTypeface(null,Typeface.BOLD)})
   card.addView(TextView(this).apply{text=b;textSize=13f;setTextColor(Color.LTGRAY)})
   catalog.addView(card,LinearLayout.LayoutParams(-1,-2).apply{bottomMargin=5})
  }
 }
 private fun log(s:String){
  ui.post{
   val entry=java.text.SimpleDateFormat("HH:mm:ss",java.util.Locale.getDefault()).format(java.util.Date())+"  "+s
   events.add(entry);if(events.size>200)events.removeAt(0)
   if(::logView.isInitialized)logView.text=entry
  }
 }
 private fun showLog(){
  AlertDialog.Builder(this).setTitle("Журнал Bluetooth и печати").setMessage(events.joinToString("\\n").ifEmpty{"Пока пусто"}).setPositiveButton("Закрыть",null).show()
 }
 private fun edit(a:String,b:String){
  val layout=LinearLayout(this).apply{orientation=1;setPadding(24,0,24,0)}
  val title=EditText(this).apply{setText(a);hint="Категория"}
  val detail=EditText(this).apply{setText(b);hint="Примеры"}
  layout.addView(title);layout.addView(detail)
  AlertDialog.Builder(this).setTitle("Наклейка").setView(layout)
   .setPositiveButton("Добавить"){_,_->if(title.text.isNotBlank()){queue.add(Pair(title.text.toString(),detail.text.toString()));updateCount();log("Добавлена этикетка: "+title.text)}}
   .setNegativeButton("Отмена",null).show()
 }
 private fun updateCount(){
  counter.text="Очередь: "+queue.size+" наклеек · "+LabelLogic.sheetCount(queue.size)+" листов\n"+queue.take(12).joinToString(" · "){it.first}
 }
 private fun toast(s:String){Toast.makeText(this,s,Toast.LENGTH_LONG).show()}
 private fun choosePrinter(){
  if(Build.VERSION.SDK_INT>=31&&checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED){
   requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT),1);return
  }
  val adapter=(getSystemService(BLUETOOTH_SERVICE) as BluetoothManager).adapter
  if(adapter==null||!adapter.isEnabled){toast("Включи Bluetooth");return}
  val devices=adapter.bondedDevices.toList()
  if(devices.isEmpty()){toast("Сначала сопряги принтер в настройках Android");return}
  AlertDialog.Builder(this).setTitle("Сопряжённые устройства")
   .setItems(devices.map{(it.name?:"Без имени")+" ("+it.address+")"}.toTypedArray()){_,i->
    printer=devices[i];status.text="Выбран: "+devices[i].name;log("Выбран принтер: "+devices[i].name+" "+devices[i].address)
   }.show()
 }
 private fun showDiagnostics(){
  val granted=Build.VERSION.SDK_INT<31||checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)==PackageManager.PERMISSION_GRANTED
  val adapter=(getSystemService(BLUETOOTH_SERVICE) as BluetoothManager).adapter
  log("Разрешение Bluetooth: "+granted+"; адаптер включён: "+(adapter?.isEnabled==true))
  val options=arrayOf("Подключение","TSPL — текст","CPCL — текст","ESC/POS — текст","TSPL — изображение","CPCL — изображение","ESC/POS — изображение","Запрос идентификатора")
  AlertDialog.Builder(this).setTitle("Диагностика · Bluetooth "+if(granted)"разрешён" else "нет доступа")
   .setItems(options){_,i->runDiagnostic(i)}
   .setNegativeButton("Закрыть",null).show()
 }
 private fun runDiagnostic(index:Int){
  val device=printer?:run{toast("Сначала выбери принтер");return}
  if(diagnosticBusy){toast("Предыдущий тест ещё выполняется");return}
  diagnosticBusy=true
  thread{
   var socket:BluetoothSocket?=null
   try{
    socket=device.createRfcommSocketToServiceRecord(UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"))
    socket.connect();log("Диагностика "+index+": подключено")
    val data=when(index){
     0->byteArrayOf()
     1->"SIZE 75 mm,40 mm\r\nGAP 2 mm,0 mm\r\nCLS\r\nTEXT 30,40,\"3\",0,2,2,\"TEST TSPL\"\r\nPRINT 1\r\n".toByteArray(Charsets.US_ASCII)
     2->"! 0 200 200 320 1\r\nTEXT 4 0 30 40 TEST CPCL\r\nFORM\r\nPRINT\r\n".toByteArray(Charsets.US_ASCII)
     3->byteArrayOf(27,64)+"TEST ESC/POS\n\n".toByteArray(Charsets.US_ASCII)
     4->page(listOf(Pair("TEST TSPL","IMAGE")))
     5->diagnosticBitmap(true)
     6->diagnosticBitmap(false)
     else->byteArrayOf(29,73,65)
    }
    if(data.isNotEmpty()){
     socket.outputStream.write(data);socket.outputStream.flush()
     log("Диагностика "+index+": отправлено "+data.size+" байт; результат печати не подтверждён")
    }
    if(index==7){
     Thread.sleep(350)
     try{
      val b=ByteArray(128);val n=if(socket.inputStream.available()>0)socket.inputStream.read(b) else 0
      if(n>0)log("Ответ HEX: "+b.take(n).joinToString(" "){"%02X".format(it)}) else log("Ответ отсутствует")
     }catch(e:Exception){log("Ответ не получен: "+e.javaClass.simpleName)}
    }
   }catch(e:Exception){log("Диагностика "+index+": "+e.javaClass.simpleName+": "+e.message)}
   finally{try{socket?.close()}catch(_:Exception){};diagnosticBusy=false;log("Диагностика "+index+": завершена")}
  }
 }
 private fun diagnosticBitmap(cpcl:Boolean):ByteArray{
  val w=384;val h=96;val bits=ByteArray(w/8*h)
  for(y in 8 until 80)for(x in 8 until 180)
   if(x<12||x>175||y<12||y>75)LabelLogic.setBlackPixel(bits,w,x,y)
  val out=ByteArrayOutputStream()
  if(cpcl){
   out.write("! 0 200 200 160 1\r\nEG 48 96 0 0 ".toByteArray(Charsets.US_ASCII))
   out.write(bits.joinToString(""){"%02X".format(it)}.toByteArray(Charsets.US_ASCII))
   out.write("\r\nFORM\r\nPRINT\r\n".toByteArray(Charsets.US_ASCII))
  }else{
   out.write(byteArrayOf(27,64,29,118,48,0,48,0,96,0))
   out.write(bits);out.write(byteArrayOf(10,10))
  }
  return out.toByteArray()
 }
 private fun print(test:Boolean){
  val dev=printer?:run{toast("Выбери принтер");return}
  if(!test&&queue.isEmpty()){toast("Очередь пуста");return}
  val pages=if(test)listOf(listOf(Pair("ТЕСТ ПЕЧАТИ","AIYIN IP-802BT"),Pair("ЭЛЕКТРОНИКА","Кабели · зарядки"),Pair("ДЕТСКИЕ ВЕЩИ","Одежда · игрушки"))) else LabelLogic.pages(queue)
  status.text="Подключение…";log("Начало печати: тест="+test+", листов="+pages.size)
  thread{
   try{
    val adapter=(getSystemService(BLUETOOTH_SERVICE) as BluetoothManager).adapter
    val socket=dev.createRfcommSocketToServiceRecord(UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"))
    try{
     log("RFCOMM: подключение к "+dev.address);socket.connect();log("RFCOMM: соединение установлено")
     pages.forEachIndexed{index,labels->val bytes=page(labels);log("Отправка листа "+(index+1)+": "+bytes.size+" байт");socket.outputStream.write(bytes);socket.outputStream.flush();log("Лист "+(index+1)+": данные отправлены");Thread.sleep(900)}
     ui.post{status.text="Команды отправлены. Проверь печать."}
    }finally{socket.close();log("Соединение закрыто")}
   }catch(e:Exception){log("ОШИБКА: "+e.javaClass.simpleName+": "+e.message);ui.post{status.text="Ошибка: "+e.javaClass.simpleName+": "+e.message}}
  }
 }
 private fun page(labels:List<Pair<String,String>>):ByteArray{
  val w=LabelLogic.WIDTH_DOTS;val h=LabelLogic.HEIGHT_DOTS;val bitmap=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888)
  val canvas=Canvas(bitmap);canvas.drawColor(Color.WHITE)
  val p=Paint(Paint.ANTI_ALIAS_FLAG).apply{color=Color.BLACK;typeface=Typeface.DEFAULT_BOLD;textSize=34f}
  labels.forEachIndexed{index,pair->
   val y=index*LabelLogic.LABEL_HEIGHT_DOTS
   canvas.drawRect(20f,(y+16).toFloat(),580f,(y+21).toFloat(),p)
   drawText(canvas,p,pair.first,28f,(y+115).toFloat())
   drawText(canvas,p,pair.second,28f,(y+195).toFloat())
   if(index<2){p.color=Color.GRAY;var x=20f;while(x<580f){canvas.drawLine(x,(y+319).toFloat(),x+12f,(y+319).toFloat(),p);x+=22f};p.color=Color.BLACK}
  }
  val rowBytes=LabelLogic.rowBytes(w);val bits=ByteArray(rowBytes*h)
  for(y in 0 until h)for(x in 0 until w){
   val c=bitmap.getPixel(x,y)
   if((Color.red(c)*299+Color.green(c)*587+Color.blue(c)*114)/1000<150){
    LabelLogic.setBlackPixel(bits,w,x,y)
   }
  }
  bitmap.recycle()
  return ByteArrayOutputStream().apply{
   write("SIZE 75 mm,120 mm\r\nGAP 2 mm,0 mm\r\nDIRECTION 1\r\nCLS\r\n".toByteArray(Charsets.US_ASCII))
   write(("BITMAP 0,0,"+rowBytes+","+h+",0,").toByteArray(Charsets.US_ASCII))
   write(bits);write("\r\nPRINT 1,1\r\n".toByteArray(Charsets.US_ASCII))
  }.toByteArray()
 }
 private fun drawText(c:Canvas,p:Paint,s:String,x:Float,y:Float){
  p.textSize=34f;while(p.measureText(s)>540f&&p.textSize>16f)p.textSize-=1f
  c.drawText(s,x,y,p)
 }
}