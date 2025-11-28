using Sandbox;
using Sandbox.Citizen;
using System.Linq; // Нужно для поиска компонентов в списках (FirstOrDefault)

public sealed class ChairLogic : Component
{
	// =========================================================
	// НАСТРОЙКИ В ИНСПЕКТОРЕ
	// =========================================================

	// Смещение игрока относительно центра стула (Local Space).
	// Z отвечает за высоту посадки (физическую).
	[Property, Group( "Position" )] public Vector3 SitOffset { get; set; } = new Vector3( 0, 0, 10 );

	// Точка высадки. Куда телепортировать игрока, когда он встанет.
	[Property, Group( "Position" )] public Vector3 ExitOffset { get; set; } = new Vector3( 50, 0, 0 );

	// Ползунок для настройки визуальной высоты анимации (sit_offset_height).
	// Это меняет только анимацию, не физический коллайдер.
	[Property, Group( "Animation" ), Range( -50, 50 )] public float SitAnimHeight { get; set; } = 10.0f;

	// Ограничение поворота головы вверх/вниз (в градусах).
	[Property, Group( "Camera" )] public float PitchClamp { get; set; } = 80.0f;

	// Дистанция камеры в режиме 3-го лица.
	[Property, Group( "Camera" )] public float ThirdPersonDistance { get; set; } = 120.0f;

	// =========================================================
	// ВНУТРЕННИЕ ПЕРЕМЕННЫЕ
	// =========================================================

	// Ссылка на игрока, который сейчас сидит. Если null — стул свободен.
	private GameObject _currentUser;

	// Храним текущие углы поворота камеры (Pitch, Yaw).
	private Angles _currentLookAngles;

	// Флаг режима камеры (false = 1-е лицо, true = 3-е лицо).
	private bool _isThirdPerson = false;

	// Таймер для ограничения частоты логов (чтобы не спамить в Update).
	private TimeSince _lastDebugLog;

	// =========================================================
	// ГЛАВНЫЙ ЦИКЛ (OnUpdate)
	// =========================================================
	protected override void OnUpdate()
	{
		// Проверяем нажатие кнопки действия (обычно "E").
		if ( Input.Pressed( "use" ) )
		{
			// Если кто-то сидит (и это мы), то встаем.
			if ( _currentUser.IsValid() ) StandUp();
			// Иначе пробуем сесть.
			else TrySit();
		}

		// Переключение камеры на кнопку "L" (только если сидим).
		if ( _currentUser.IsValid() && Input.Pressed( "l" ) )
		{
			_isThirdPerson = !_isThirdPerson;
			Log.Info( $"[ChairLogic] Camera Mode switched. Third Person: {_isThirdPerson}" );
		}

		// Если игрок сидит, обновляем камеру и анимацию каждый кадр.
		if ( _currentUser.IsValid() )
		{
			UpdateCamera();
			UpdateSittingAnimation();
		}
	}

	// =========================================================
	// ЛОГИКА АНИМАЦИИ
	// =========================================================
	private void UpdateSittingAnimation()
	{
		// Ищем помощника анимации (CitizenAnimationHelper) в потомках игрока (обычно на модели).
		var animator = _currentUser.Components.GetInDescendantsOrSelf<CitizenAnimationHelper>();

		// Ищем рендерер модели для прямой записи параметров в граф.
		var renderer = _currentUser.Components.GetInDescendantsOrSelf<SkinnedModelRenderer>();

		if ( animator != null )
		{
			// Основной флаг "Сидим".
			animator.IsSitting = true;
			// Уточняем стиль: Стул.
			animator.Sitting = CitizenAnimationHelper.SittingStyle.Chair;

			// Обнуляем скорость анимации, чтобы ноги не бежали на месте.
			animator.WithVelocity( Vector3.Zero );
			animator.WithWishVelocity( Vector3.Zero );

			// Синхронизируем направление головы с камерой.
			if ( Scene.Camera != null )
				animator.WithLook( Scene.Camera.WorldRotation.Forward );
		}

		// Прямая запись параметров в Animation Graph (Грубая сила).
		if ( renderer != null )
		{
			renderer.Set( "sit", 1 ); // 1 = Chair
			renderer.Set( "sit_offset_height", SitAnimHeight ); // Твоя настройка высоты
		}
	}

	// =========================================================
	// ПОПЫТКА СЕСТЬ (TrySit)
	// =========================================================
	private void TrySit()
	{
		var camera = Scene.Camera;
		if ( camera == null ) return;

		// Ищем корневой объект игрока через физику (Rigidbody).
		var playerBody = camera.Components.GetInAncestorsOrSelf<Rigidbody>();
		if ( playerBody == null ) return;

		var playerObject = playerBody.GameObject;

		// Пускаем луч из глаз.
		var rayStart = camera.WorldPosition;
		var rayEnd = camera.WorldPosition + camera.WorldRotation.Forward * 200;

		var trace = Scene.Trace.Ray( rayStart, rayEnd )
			.IgnoreGameObjectHierarchy( camera.GameObject )
			.IgnoreGameObjectHierarchy( playerObject )
			.WithoutTags( "player", "trigger" );

		var ray = trace.Run();

		// Если попали в ЭТОТ стул.
		if ( ray.Hit && ray.GameObject == GameObject )
		{
			SitDown( playerObject );
		}
	}

	// =========================================================
	// ПРОЦЕСС ПОСАДКИ (SitDown)
	// =========================================================
	private void SitDown( GameObject player )
	{
		Log.Info( $"[ChairLogic] --- SitDown Start ---" );
		_currentUser = player;
		_isThirdPerson = false; // Сброс на 1-е лицо

		// Запоминаем текущий угол камеры.
		if ( Scene.Camera != null )
			_currentLookAngles = Scene.Camera.WorldRotation.Angles();

		// Отключаем физику (используем FindMode, на всякий случай).
		var rb = player.Components.Get<Rigidbody>( FindMode.EverythingInSelf );
		if ( rb != null ) rb.Enabled = false;

		// Отключаем контроллер движения.
		var controller = player.Components.GetAll<Component>( FindMode.EverythingInSelf )
			.FirstOrDefault( c => c.GetType().Name == "PlayerController" || c.GetType().Name == "CharacterController" );

		if ( controller != null ) controller.Enabled = false;

		// Прикрепляем игрока к стулу.
		player.SetParent( GameObject );
		player.LocalPosition = SitOffset;
		player.LocalRotation = Rotation.Identity;

		Log.Info( $"[ChairLogic] Player attached." );
	}

	// =========================================================
	// ПРОЦЕСС ВСТАВАНИЯ (StandUp)
	// =========================================================
	private void StandUp()
	{
		if ( !_currentUser.IsValid() ) return;

		var player = _currentUser;
		Log.Info( "==================================================" );
		Log.Info( $"[ChairLogic DEBUG] STANDUP: {player.Name}" );

		// 1. Убираем родителя (отцепляем от стула).
		player.SetParent( null );

		// 2. Телепортация на точку выхода (+10 вверх для безопасности).
		var exitPos = WorldPosition + (WorldRotation * ExitOffset) + Vector3.Up * 10.0f;
		player.WorldPosition = exitPos;

		// Поворачиваем игрока туда, куда он смотрел.
		player.WorldRotation = Rotation.FromYaw( _currentLookAngles.yaw );

		// 3. СБРОС КАМЕРЫ.
		// Возвращаем камеру в дефолтное положение (0,0,64) относительно игрока.
		if ( Scene.Camera != null )
		{
			// Если камера потерялась, возвращаем её игроку.
			if ( Scene.Camera.GameObject.Parent != player )
				Scene.Camera.GameObject.SetParent( player );

			Scene.Camera.LocalPosition = new Vector3( 0, 0, 64 );
			Scene.Camera.LocalRotation = Rotation.Identity;
		}

		// 4. ВКЛЮЧАЕМ КОНТРОЛЛЕР.
		// ВАЖНО: Используем FindMode.EverythingInSelf, потому что компонент сейчас Disabled!
		var controller = player.Components.GetAll<Component>( FindMode.EverythingInSelf )
			.FirstOrDefault( c => c.GetType().Name == "PlayerController" || c.GetType().Name == "CharacterController" );

		if ( controller != null )
		{
			controller.Enabled = true;
			Log.Info( $"[ChairLogic DEBUG] Controller '{controller.GetType().Name}' RE-ENABLED." );
		}
		else
		{
			Log.Error( "[ChairLogic DEBUG] CRITICAL: Controller NOT found (even with FindMode.EverythingInSelf)!" );
		}

		// 5. ВКЛЮЧАЕМ ФИЗИКУ.
		var rb = player.Components.Get<Rigidbody>( FindMode.EverythingInSelf );
		if ( rb != null )
		{
			rb.Enabled = true;
			rb.Velocity = Vector3.Zero; // Гасим инерцию
			rb.AngularVelocity = Vector3.Zero;
			Log.Info( "[ChairLogic DEBUG] Rigidbody RE-ENABLED." );
		}

		_currentUser = null;
		Log.Info( "==================================================" );
	}

	// =========================================================
	// УПРАВЛЕНИЕ КАМЕРОЙ (UpdateCamera)
	// =========================================================
	private void UpdateCamera()
	{
		if ( Scene.Camera == null ) return;

		// Считываем мышь.
		var lookInput = Input.AnalogLook;

		// Обновляем углы.
		_currentLookAngles.pitch += lookInput.pitch;
		_currentLookAngles.yaw += lookInput.yaw;
		_currentLookAngles.pitch = _currentLookAngles.pitch.Clamp( -PitchClamp, PitchClamp );

		// Применяем вращение.
		var rotation = _currentLookAngles.ToRotation();
		Scene.Camera.WorldRotation = rotation;

		// Расчет позиции (глаза).
		var eyePosition = _currentUser.WorldPosition + Vector3.Up * 64.0f;

		// Логика 3-го лица.
		if ( _isThirdPerson )
		{
			var camForward = rotation.Forward;
			var camPos = eyePosition - (camForward * ThirdPersonDistance);

			// Проверка на столкновение со стенами.
			var tr = Scene.Trace.Ray( eyePosition, camPos )
				.IgnoreGameObjectHierarchy( _currentUser )
				.IgnoreGameObjectHierarchy( GameObject )
				.Radius( 5.0f )
				.Run();

			Scene.Camera.WorldPosition = tr.EndPosition;
		}
		else
		{
			// 1-е лицо.
			Scene.Camera.WorldPosition = eyePosition;
		}
	}
}
