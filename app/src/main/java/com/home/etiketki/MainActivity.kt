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
 private var printer:BluetoothDevice?=null
 private val ui=Handler(Looper.getMainLooper())
 override fun onCreate(savedInstanceState:Bundle?){
  super.onCreate(savedInstanceState)
  val root=LinearLayout(this).apply{orientation=1;setPadding(20,20,20,20)}
  setContentView(ScrollView(this).apply{addView(root)})
  root.addView(TextView(this).apply{text="Этикетки";textSize=28f})
  root.addView(TextView(this).apply{text="75 × 120 мм · по три на листе · тест TSPL"})
  status=TextView(this).apply{text="Принтер не выбран"};root.addView(status)
  button(root,"Выбрать Bluetooth-принтер"){choosePrinter()}
  val search=EditText(this).apply{hint="Поиск категорий";setSingleLine(true)};root.addView(search)
  catalog=LinearLayout(this).apply{orientation=1};root.addView(catalog)
  counter=TextView(this);root.addView(counter)
  button(root,"Добавить свою наклейку"){edit("","")}
  button(root,"Очистить очередь"){queue.clear();updateCount()}
  button(root,"Напечатать тест"){print(true)}
  button(root,"Напечатать очередь"){print(false)}
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
  parent.addView(Button(this).apply{text=label;setOnClickListener{fn()}})
 }
 private fun render(q:String){
  catalog.removeAllViews()
  items.filter{it.first.contains(q,true)||it.second.contains(q,true)}.forEach{(a,b)->
   button(catalog,a+" · "+b){edit(a,b)}
  }
 }
 private fun edit(a:String,b:String){
  val layout=LinearLayout(this).apply{orientation=1;setPadding(24,0,24,0)}
  val title=EditText(this).apply{setText(a);hint="Категория"}
  val detail=EditText(this).apply{setText(b);hint="Примеры"}
  layout.addView(title);layout.addView(detail)
  AlertDialog.Builder(this).setTitle("Наклейка").setView(layout)
   .setPositiveButton("Добавить"){_,_->if(title.text.isNotBlank()){queue.add(Pair(title.text.toString(),detail.text.toString()));updateCount()}}
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
    printer=devices[i];status.text="Выбран: "+devices[i].name
   }.show()
 }
 private fun print(test:Boolean){
  val dev=printer?:run{toast("Выбери принтер");return}
  if(!test&&queue.isEmpty()){toast("Очередь пуста");return}
  val pages=if(test)listOf(listOf(Pair("ТЕСТ ПЕЧАТИ","AIYIN IP-802BT"),Pair("ЭЛЕКТРОНИКА","Кабели · зарядки"),Pair("ДЕТСКИЕ ВЕЩИ","Одежда · игрушки"))) else LabelLogic.pages(queue)
  status.text="Подключение…"
  thread{
   try{
    val adapter=(getSystemService(BLUETOOTH_SERVICE) as BluetoothManager).adapter
    adapter.cancelDiscovery()
    val socket=dev.createRfcommSocketToServiceRecord(UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"))
    try{
     socket.connect()
     pages.forEach{socket.outputStream.write(page(it));socket.outputStream.flush();Thread.sleep(900)}
     ui.post{status.text="Команды отправлены. Проверь печать."}
    }finally{socket.close()}
   }catch(e:Exception){ui.post{status.text="Ошибка: "+e.javaClass.simpleName+": "+e.message}}
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